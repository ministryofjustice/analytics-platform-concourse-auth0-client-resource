[![Docker Repository on Quay](https://quay.io/repository/mojanalytics/concourse-auth0-resource/status "Docker Repository on Quay")](https://quay.io/repository/mojanalytics/concourse-auth0-resource)

# Auth0 Client Resource

Provides a Concourse resource to get and create Auth0 Clients. Used to create a
Client on the fly when deploying a webapp on the Analytical Platform, allowing
authentication delegation to Auth0 using OTP emails.

## Resource configuration

These parameters go into the `source` fields of the resource type. Bold items are required:

| Parameter | Description |
| --------- | ----------- |
| **`client-id`** | Auth0 client ID for authentication to the Management API |
| **`client-secret`** | Auth0 client secret for authentication to the Management API |
| **`domain`** | Auth0 client domain for authentication to the Management API |
| **`authz-url`** | Base URL of the Auth0 Authorization Extension API |
| **`authz-audience`** | API Audience of the Auth0 Authorization Extension API |

# Behaviour

### `check`: Not Supported

### `in`: Retrieve Client Details

Fetches the client ID and secret.

**Parameters**

+ `name`: _Required_. The name of the client.
+ `domain`: _Required_. The domain of the client, such that the OIDC well-known
  URLS are located at `https://{name}.{domain}/.well-known`

### `out`: Create Client

Creates a client with the specified name if it does not exist.

**Parameters**

+ `name`: _Required_. The name of the client.
+ `domain`: _Required_. The domain of the client, such that the OIDC well-known
  URLS are located at `https://{name}.{domain}/.well-known`

## Installation

This resource is not included with Concourse CI. You must integrate this resource in the `resource_types` section of your pipeline.

```yaml
resource_types:
- name: auth0-client
  type: docker-image
  source:
    repository: quay.io.mojanalytics/concourse-auth0-resource
    tag: 0.1.0

resources:
- name: webapp-auth0-client
  type: auth0-client
  source:
    client-id: ((auth0-client-id))
    client-secret: ((auth0-client-secret))
    domain: ((auth0-domain))
    authz-url: ((auth0-authz-url))
    authz-audience: ((auth0-authz-audience))

jobs:
- name: deploy
  plan:
  - put: webapp-auth0-client
    params:
      name: ((client-name))
      domain: ((client-domain))
```

## Contributing

1. Fork it!
2. Create your feature branch: `git checkout -b feature/new-feature`
3. Commit your changes: `git commit -am 'Add some feature'`
4. Push to the branch: `git push origin feature/new-feature`
5. Submit a pull request.

## License

[MIT Licence (MIT)](LICENCE)
