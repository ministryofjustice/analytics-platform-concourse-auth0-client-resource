from auth0.v3 import authentication, exceptions
import requests
import structlog


structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ]
)
log = structlog.get_logger()

# Auth0 Management API 'per_page' parameter used for pagination
# This is the maximum they'll allow: https://auth0.com/docs/product-lifecycle/deprecations-and-migrations/migrate-to-paginated-queries
PER_PAGE = 50


class AccessTokenError(Exception):
    pass


class CreateResourceError(Exception):
    pass


class UpdateResourceError(Exception):
    pass


class Auth0Error(Exception):
    pass


class Auth0(object):
    def __init__(self, client_id, client_secret, domain):
        self.client_id = client_id
        self.client_secret = client_secret
        self.domain = domain
        self.apis = {}

    def access_token(self, audience):

        get_token = authentication.GetToken(self.domain)

        try:
            token = get_token.client_credentials(
                self.client_id, self.client_secret, audience
            )

        except exceptions.Auth0Error as error:
            log.msg(
                "Access token error.",
                exc_info=error,
                client_id=self.client_id,
                domain=self.domain,
            )
            raise AccessTokenError(error, self.client_id, self.domain, audience)

        return token["access_token"]

    def access(self, api):
        key = api.__class__.__name__.replace("API", "").lower()
        api.access_token = self.access_token(api.audience)
        setattr(self, key, api)


class API(object):
    def __init__(self, base_url, audience=None, use_pagination=False):
        self.base_url = base_url.rstrip("/")
        self.audience = audience or base_url
        # pagination is optional as different APIs may not support it
        # e.g. Authorization extension API doesn't support `page`/`per_page`
        # params and it would respond with a `400 BAD REQUEST` if these are
        # passed.
        self.use_pagination = use_pagination
        self.access_token = None
        self._token = None

    def request(self, method, endpoint, **kwargs):
        url = "{base_url}/{endpoint}".format(base_url=self.base_url, endpoint=endpoint)
        params = kwargs.get("params", {})

        log.msg(
            "Calling endpoint.",
            method=method,
            url=url,
            params=params,
            base_url=self.base_url,
            endpoint=endpoint,
        )

        request_args = {
            "headers": {
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
            "params": params,
        }

        # Only send a payload with POST/PUT or API will respond with 5xx.
        if method in ("POST", "PUT", "PATCH"):
            request_args["json"] = kwargs.get("json", {})

        response = requests.request(method, url, **request_args)

        # If there's an error, log it then re-raise.
        try:
            response.raise_for_status()
        except Exception as ex:
            log.msg(
                "Auth0 API error.",
                exc_info=ex,
                url=url,
                base_url=self.base_url,
                endpoint=endpoint,
                method=method,
                status=response.status_code,
                content=response.text,
            )
            raise ex

        # No error? Good to go with the JSON payload.
        if response.text:
            return response.json()

        # Some responses don't have a JSON payload so return a false-y
        # empty dictionary that won't cause undesirable side-effects.
        return {}

    def create(self, resource):
        endpoint = "{}s".format(resource.__class__.__name__.lower())

        response = self.request("POST", endpoint, json=resource)

        if "error" in response:
            log.msg("Error creating resource.", response=response)
            raise CreateResourceError(response)

        return resource.__class__(self, response)

    def update(self, resource):
        endpoint = "{}s".format(resource.__class__.__name__.lower())

        response = self.request("PATCH", endpoint, json=resource)

        if "error" in response:
            log.msg("Error updating resource.", response=response)
            raise UpdateResourceError(response)

        return resource.__class__(self, response)

    def get_all(self, resource_class):
        endpoint = "{}s".format(resource_class.__name__.lower())

        items = []
        total = None

        params = {}
        if self.use_pagination:
            params = {
                "include_totals": "true",
                "page": 0,
                "per_page": PER_PAGE,
            }

        while True:
            response = self.request("GET", endpoint, params=params)

            if "total" not in response:
                raise Auth0Error(f"get_all {endpoint}: Missing 'total' property")

            if endpoint not in response:
                raise Auth0Error(f"get_all {endpoint}: Missing '{endpoint}' property")

            if total is None:
                total = response["total"]

            if total != response["total"]:
                raise Auth0Error(f"get_all {endpoint}: Total changed")

            # response will look like `{"clients": [...], "total": 42}`
            items.extend(response[endpoint])

            if not self.use_pagination:
                break

            if len(items) >= total:
                break

            if len(response[endpoint]) < 1:
                break

            params["page"] += 1

        return [resource_class(self, item) for item in items]

    def get(self, resource):
        resources = self.get_all(resource.__class__)

        for other in resources:
            if all(pair in other.items() for pair in resource.items()):
                return other

    def get_or_create(self, resource):
        result = self.get(resource)

        if result is None:
            result = self.create(resource)

        return result


class ManagementAPI(API):
    def __init__(self, domain):
        super(ManagementAPI, self).__init__(
            "https://{domain}/api/v2/".format(domain=domain), use_pagination=True,
        )


class AuthorizationAPI(API):
    pass


class Resource(dict):
    def __init__(self, api=None, *args, **kwargs):
        super(Resource, self).__init__(*args, **kwargs)
        self.api = api

    def update(self, **overrides):
        super().update(overrides)
        return self.api.update(self)


class Client(Resource):
    def __init__(self, api=None, *args, **kwargs):
        super(Client, self).__init__(api, *args, **kwargs)
        self["app_type"] = "regular_web"

    def disable_all_connections(self, ignore=[]):
        ignore = [connection["id"] for connection in ignore]

        connections = self.api.get_all(Connection)

        for connection in connections:

            if connection["id"] in ignore:
                continue

            if self["client_id"] in connection["enabled_clients"]:
                connection.disable_client(self)


class Connection(Resource):
    def disable_client(self, client):

        if client["client_id"] in self["enabled_clients"]:
            self["enabled_clients"].remove(client["client_id"])

            self.api.request(
                "PATCH",
                "connections/{id}".format(**self),
                json={"enabled_clients": self["enabled_clients"]},
            )


class AuthzResource(Resource):
    def __init__(self, api=None, *args, **kwargs):
        super(AuthzResource, self).__init__(api, *args, **kwargs)

        if "description" not in self and "name" in self:
            self["description"] = self["name"]


class Permission(AuthzResource):
    def __init__(self, api=None, *args, **kwargs):
        super(Permission, self).__init__(api, *args, **kwargs)
        self["applicationType"] = "client"


class Role(AuthzResource):
    def __init__(self, api=None, *args, **kwargs):
        super(Role, self).__init__(api, *args, **kwargs)
        self["applicationType"] = "client"

    def __getitem__(self, key):

        if key == "permissions":

            if not self.__contains__(key):
                return []

        return super(Role, self).__getitem__(key)

    def add_permission(self, permission):

        if permission["_id"] in self["permissions"]:
            return

        if "permissions" not in self:
            self["permissions"] = []

        self["permissions"].append(permission["_id"])

        self.api.request(
            "PUT",
            "roles/{_id}".format(**self),
            json={
                "name": self["name"],
                "description": self["description"],
                "applicationId": self["applicationId"],
                "applicationType": self["applicationType"],
                "permissions": self["permissions"],
            },
        )


class Group(AuthzResource):
    def add_role(self, role):
        self.api.request(
            "PATCH", "groups/{_id}/roles".format(**self), json=[role["_id"]]
        )
