# Mistifi

Is a RESTAPI client used for interfacing with Mist (Juniper) API.

## Motivation


# Installation

The module can be pip installed

```
pip install mistifi
```
or using `pip3` if using python3.

The module is imported with
```python
import mistifi
```

# Usage

The usage workflow intended is:
1. Create an instance with passing in the cloud and authentication options.
2. Initiate communication with the `comms()` method.
3. Use the `resource()` method or 

When creating an instance pass in the `cloud` option to specify a direct instance of a cloud. If not passed in, the default `US` will be used.

## Selecting a cloud
There are currently two cloud options to select from. Either `EU` or `US`, with `US` being the default if not provided with the `cloud` attribute.
They default to
- US = api.mist.com
- EU = api.eu.mist.com

**Ex. 1: Using the default `US` cloud**
```python
>>> mist = MMClient()
```
**Ex. 2: Specifying the `EU` cloud**
```python
>>> mist = MMClient(cloud="EU")
```
Note that using either caps or not for the value will work. In the below example the `US` cloud will be used.
```python
>>> mist = MMClient(cloud="us")
```
## Using a token or username/password

**Ex. 1: Using a token**

In below example a token `thetoken` is used with the US cloud. You can create a user token by following [these instructions](https://www.mist.com/documentation/using-postman/)
```python
>>> mist = MMClient(token="thetoken")
```
An alternative with specifying the EU cloud would be.
```python
>>> mist = MMClient(cloud="EU", token="thetoken")
```
The token always has preference before username/password or other option, so in the below example a token would be used.
```python
>>> mist = MMClient(, token="thetoken", username="theuser@mistifi.com", password="thepass")
```

**Ex. 2: Using username and password.**

Currently 2FA and OAUTH aren't supported.

The minimum required for this option is to create an instance without any attributes like below.
```python
>>> mist = MMClient()
```
In this case you are asked for username and password.

You can provide one or both when creating a new instance and be asked about the other once the `comms()` method is run.

```python
>>> mist = MMClient(cloud='us', username="theuser@mistifi.com")
```

## Communicating with the cloud
Once the cloud and authentication options are selected you must run the `comms()` method which correctly sets up the headers depending on the authentication method used. For example `X-CSRFTOKEN` is setup for the username/password option.
```python
>>> mist = comms()
```

## Interfacing with the cloud URIs
If a specific resource method for a specific URI is not defined the main method that can be used is the `resource()` one.


# Debugging 

The default debug level is `ERROR`, which can be changed per method call by preempting it with `logzero.loglevel(logging.LEVEL)` where `LEVEL` is the debug level.

**Ex. 1: DEBUG level**
```python
>>> logzero.loglevel(logging.DEBUG)
>>> mist_user.whoami()

[I 200326 14:48:17 mistifi:547] Calling whoami()
[I 200326 14:48:17 mistifi:548] kwargs in: {}
[I 200326 14:48:17 mistifi:511] Calling resource()
[D 200326 14:48:17 mistifi:512] kwargs in: {'uri': '/self'}
[I 200326 14:48:17 mistifi:471] Calling _params()
[I 200326 14:48:17 mistifi:472] kwargs in: {'uri': '/self'}
[D 200326 14:48:17 mistifi:479] Returned params: {}
[I 200326 14:48:17 mistifi:395] Calling _resource_url()
[I 200326 14:48:17 mistifi:396] kwargs in: {'uri': '/self'}
[D 200326 14:48:17 mistifi:450] URL to endpoint: https://api.mist.com/api/v1/self
[I 200326 14:48:17 mistifi:333] Calling _api_call()
[I 200326 14:48:17 mistifi:334] Method is: GET
[I 200326 14:48:17 mistifi:335] Calling URL: https://api.mist.com/api/v1/self
[D 200326 14:48:17 mistifi:336] With headers: {'Content-Type': 'application/json', 'Accept': 'application/json'}
[I 200326 14:48:18 mistifi:346] Response status code: 200
[D 200326 14:48:18 mistifi:356] Response HEAD: {'Access-Control-Allow-Credentials': 'true', 'Access-Control-Allow-Origin': 'https://manage.mist.com', 'Access-Control-Expose-Headers': 'X-CSRFTOKEN,X-Requested-With,X-Page-Page,X-Page-Total', 'Allow': 'GET, OPTIONS, DELETE, PUT', 'Cache-Control': 'no-cache, no-store', 'Content-Type': 'application/json', 'Date': 'Thu, 26 Mar 2020 14:48:18 GMT', 'Pragma': 'no-cache', 'Server': 'gunicorn/19.10.0', 'Set-Cookie': 'sessionid=8trv1zr79sknwk0n7sz2pim8x26g84mh; Domain=.mist.com; expires=Fri, 27-Mar-2020 14:48:18 GMT; HttpOnly; Max-Age=86400; Path=/; Secure', 'Vary': 'Origin', 'Via': 'kong/0.9.3', 'X-Frame-Options': 'SAMEORIGIN', 'X-Kong-Proxy-Latency': '0', 'X-Kong-Upstream-Latency': '39', 'Content-Length': '608', 'Connection': 'keep-alive'}
[D 200326 14:48:18 mistifi:357] The response: {'email': 'blah@mist.com'...}
```

**Ex. 2: INFO level**

Each method then resets logging to `ERROR`, so you need to set logging level before each one.











