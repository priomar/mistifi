import getpass
import sys
import json

import requests
from requests import Session
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from urllib.parse import urljoin

import logging
import logzero
from logzero import logger


class MistAuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class MistAPIError(Exception):
    """Raised when API calls fail."""
    pass


class MistNetworkError(Exception):
    """Raised when network connectivity issues occur - should cause application exit."""
    pass


clouds = {
    "US": "api.mist.com",
    "EU": "api.eu.mist.com",
}

# Note: Default logging level removed to allow user control

class MistiFi:
    """All Mist API URIs are found on https://api.mist.com/api/v1/docs/Home
    and are accessible if logged in

    Parameters
    ----------
    cloud: `str`, optional, default: 'US'
        Either "US" or "EU" for either 'api.mist.com' or 'api.eu.mist.com'
        clouds respectively

    token: `str`, optional
        A user's token for accessing the selected cloud (cloud specific).

    username: `str`, optional, default: None
        Username for the selected cloud (cloud specific).

    password: `str`, optional, default: None
        Password for the selected cloud (cloud specific).

    apiv: `str`, optional, default: 1
        The API version used for the calls.

    verify: `bool`, optional, default: False
        Same as requests verify, but defaults to False as most MM
        implementations are expected to not use certs. Either a boolean, in
        which case it controls whether we verify the server’s TLS
        certificate, or a string, in which case it must be a path to a CA
        bundle to use.

    timeout: `int`, optional, default: 10
        The timeout for the connection.

    Examples:
    ---------
    **Ex. 1:** Use with a token

    >>> mist = MMClient(token="thetoken")
    >>> mist.comms()

    **Ex. 2:** Usage without the token.

    In this case you are asked for username and password or you can
    provide one or both when creating a new instance.

    >>> mist = MMClient(username="theuser")
    >>> mist.comms()
    """
    def __init__(self, cloud="us", token="", username="", password="", apiv="1", verify=False, timeout=10):

        # Constructor attributes
        self.cloud = self._select_cloud(cloud)
        self.token = token
        self.username = username
        self.password = password
        self.apiv = apiv
        self.verify = bool(verify)
        self.timeout = abs(timeout)

        # Other class attributes used later
        self.csrftoken = None
        self.mist_base_api_url = f'https://{self.cloud}/'

    def comms(self):
        """The first method to be called to configure the session and to login to the Mist cloud.

        It sets up the login payload and the session headders depending on the type of login.
        """

        logger.info('Calling comms()')

        #logger.debug(f"Selected cloud: '{self.cloud}' >> '{cloud.upper()}'")
        logger.debug(f'Base URL: {self.mist_base_api_url}')

        # Configure the session with basic parameters
        self._config_session()

        #
        # If token provided, use it to log into the Mist cloud...
        #
        if self.token:
            self.session.headers['Authorization'] = f'Token {self.token}'
            logger.debug('Token added to session.headers')

        # ...otherwise prompt for user credentials if not provided
        else:
            #
            # If username not provided, ask for it
            #
            self.login_payload = {"email": None, "password": None}

            # Get the username
            if not self.username:
                self.username = input("Username (email):\x20")

            self.login_payload['email'] = self.username

            #
            # If password not provided, ask for it
            #
            if not self.password:
                #
                # If password was not provided, get it from user input
                self.password = getpass.getpass(f"Mist password for user `{self.username}` required:\x20")

            # Then set it in the login payload outside of conditional
            # as the password might have been passed in with the object
            self.login_payload['password'] = self.password
            logger.debug('Using username and password')

            # Finally login
            self._user_login(self.login_payload)

        # Note: Logging level is no longer automatically reset to allow user control

    def logout(self):
        """Logs out of the cloud, which is not really
        needed, but available anyway.

        Returns
        -------
        The HTTP JSON response
        """
        logger.info("Calling logout()")

        url_logout = self._resource_url(uri="/logout")
        resp = self._api_call("POST", url_logout)

        logger.debug(f'Logout response: {resp}')

        # Note: Logging level is no longer automatically reset to allow user control

        return resp

    def _config_session(self):
        """Session configuration for requests.Session()
        """

        logger.info(f'Calling _config_session()')

        # Setup base headers
        headers = {
            'Content-Type': 'application/json',
            'Accept' : 'application/json',
        }

        logger.debug(f'Configured Headers: {headers}')

        self.session = requests.Session()
        self.session.headers.update(headers)

        # Setup the retry strategy
        # https://findwork.dev/blog/advanced-usage-python-requests-timeouts-retries-hooks/
        retries = Retry(
            total=3,                    # Total retry attempts
            read=3,                     # Read timeout retries
            connect=2,                  # Connection retries (fewer for faster fail)
            backoff_factor=0.3,         # Exponential backoff: 0.3, 0.6, 1.2 seconds
            status_forcelist=[408, 429, 500, 502, 503, 504, 520, 522, 524],
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"],
            raise_on_redirect=False,    # Don't fail on redirects
            raise_on_status=False,      # Let our code handle status codes
        )
        self.session.mount(self.mist_base_api_url, HTTPAdapter(max_retries=retries))

        # Handle response status
        #assert_status_hook = lambda response, *args, **kwargs: response.raise_for_status()
        #self.session.hooks["response"] = [assert_status_hook]

    def _select_cloud(self, cloud):
        """Cloud selector, which either selects the specified 'cloud' or returns the default 'US' one.

        Args
        ----
        cloud: `str`
            Can be 'us' or 'eu' (caps or not doesn't matter)
        """
        logger.info("Calling _select_cloud()")

        try:
            selected_cloud = clouds[cloud.upper()]
            logger.info(f"Selected cloud: {cloud.upper()} -> {selected_cloud}")
            return selected_cloud
        except KeyError:
            logger.exception(f'Not a valid entry {list(clouds.keys())}. Using "US" as default.')
            logger.info(f"Selected cloud: US (default) -> {clouds['US']}")
            return clouds["US"]

    def _user_login(self, login_payload):
        """Method to authenticate with username/password credentials.

        Args
        ----
        login_payload: dict
            A dict with username and password credentials

        Raises
        ------
        MistAuthenticationError
            When login fails
        """
        logger.info('Calling _user_login()')

        url_login = self._resource_url(uri='/login')

        # Login with or without the 2 factor token
        resp = self.session.post(url_login, json=login_payload)

        # The headers and cookies in the response
        resp_head = resp.headers
        resp_status_code = resp.status_code
        resp_text = resp.text
        resp_jtext = json.loads(resp_text)

        # Handle error responses
        if resp_status_code >= 400:
            error_detail = resp_jtext.get('detail', 'Unknown authentication error')
            logger.error(f'Login response code: {resp.status_code}')
            logger.error(f"Response Error: {error_detail}")
            raise MistAuthenticationError(f"Login failed: {error_detail}")
        
        # Handle successful login
        jresponse = resp.json()
        logger.info(f'Login response code: {resp.status_code}')
        logger.debug(f'Response HEAD: {resp_head}')
        logger.debug(f'The response: {jresponse}')
        
        # Update headers with CSRF token for session-based authentication
        try:
            resp_csrftoken = resp.cookies['csrftoken']
            self.session.headers['X-CSRFTOKEN'] = resp_csrftoken
            logger.debug(f'Session headers updated with X-CSRFTOKEN: {self.session.headers}')
        except KeyError:
            logger.warning("No CSRF token found in response cookies")
        
        return jresponse

    def _api_call(self, method, url, timeout=30, **kwargs):
        """The API call handler with enhanced error handling.

        This method is used by `resource()`. kwargs passed in get passed to the
        requests.session instance

        Args
        ----
        method: `str`
            A valid HTTP method

        url: `str`
            URL with the endpoint included
            
        timeout: `int`, optional, default: 30
            Request timeout in seconds

        Keyword Args
        ------------
        These are passed into the requests and include the `params` and `json`
        attributes which are the exact same ones as used by requests.

        Returns:
        --------
        The response in JSON format if status code is below 400
        
        Raises:
        -------
        MistNetworkError
            When network connectivity issues occur
        MistAuthenticationError
            When authentication fails
        MistAPIError
            When API call fails with status code >= 400
        """
        logger.info("Calling _api_call()")
        logger.info(f"Method is: {method.upper()}")
        logger.info(f"Calling URL: {url}")

        try:
            # This is where the call happens
            response = getattr(self.session, method.lower())(url, timeout=timeout, **kwargs)
        except requests.exceptions.ConnectionError as e:
            if "Name or service not known" in str(e) or "nodename nor servname provided" in str(e):
                raise MistNetworkError("DNS resolution failed - check internet connection")
            # Other connection errors already handled by Retry
            raise MistNetworkError(f"Network connection failed: {e}")
        except requests.exceptions.Timeout:
            raise MistNetworkError("Request timeout - check network connectivity")

        logger.info(f"Response status code: {response.status_code}")

        # Handle error responses (after all retries exhausted)
        if response.status_code == 401:
            raise MistAuthenticationError("Authentication failed - check token")
        elif response.status_code >= 400:
            try:
                error_detail = response.json().get('detail', 'Unknown API error')
            except (json.JSONDecodeError, ValueError):
                error_detail = response.text or 'Unknown API error'
            
            logger.error(f"API Error ({response.status_code}): {error_detail}")
            raise MistAPIError(f"API call failed ({response.status_code}): {error_detail}")
        
        # Handle successful responses
        try:
            jresponse = response.json()
        except (json.JSONDecodeError, ValueError):
            raise MistAPIError("Invalid JSON response from server")
            
        logger.debug(f'Response HEAD: {response.headers}')
        logger.debug(f'The response: {jresponse}')
        return jresponse

    def _resource_url(self, **kwargs):
        """The resource URL formatter

        Will return the properly formatted URL with any provided org_id, site_id,
        uri, etc, or a combination of them all.

        URL is returned in a Mist defines hierarchy with org_id first, then site_id,
        then other IDs and URIs.

        Current special kwargs are:
            ``org_id``, ``site_id``, ``map_id``, ``wlan_id``, ``uri``, ``apitoken_id``, ``params``

        Parameters
        ----------
        org_id : str, optional
            The Organization ID of a specific organization
        site_id : str, optional
            The Site ID of a specific site
        map_id : str, optional
            The Map ID of a specific map
        wlan_id : str, optional
            The WLAN ID of a specific WLAN
        uri : str, optional
            The endpoint resource, e.g. '/self', or 'self',
            or '/self/' will all work
        apitoken_id : str, optional
            The token ID of a specific user token
        **kwargs : str, optional
            Additional values that will get added to the end
            as .../valueX, or .../valueX/valueY if more passed in

        Returns
        -------
        str
            The full URL string to the requested endpoint
        """
        logger.info("Calling _resource_url()")
        logger.info(f"kwargs in: {kwargs}")

        url = f"{self.mist_base_api_url}api/v{self.apiv}/"

        # Set of above parameters that will be skipped by the
        # for loop below so as to not add them again to the URL
        # 'params' are special and are passed to requests as params
        # so they are not precessed here.
        known_id_names = {'params'}

        # List of most used kwargs
        if 'org_id' in kwargs:
            org_id = f'orgs/{kwargs["org_id"]}'
            url = urljoin(url, org_id) + "/"
            known_id_names.add("org_id")
        if 'site_id' in kwargs:
            site_id = f'sites/{kwargs["site_id"]}'
            url = urljoin(url, site_id) + "/"
            known_id_names.add("site_id")
        if 'map_id' in kwargs:
            map_id = f"maps/{kwargs['map_id']}"
            url = urljoin(url, map_id) + "/"
            known_id_names.add("map_id")
        if 'wlan_id' in kwargs:
            wlan_id = f"wlans/{kwargs['wlan_id']}"
            url = urljoin(url, wlan_id) + "/"
            known_id_names.add("wlan_id")
        #if 'provider' in kwargs:
        #    provider_id = f"oauth/{kwargs['provider']}"
        #    url = urljoin(url, provider_id) + "/"
        #    known_id_names.add("provider")
        if 'uri' in kwargs:
            url = urljoin(url, kwargs['uri'].strip('/'))
            known_id_names.add("uri")
        if 'apitoken_id' in kwargs:
            url = urljoin(url, kwargs['apitoken_id']) + "/"
            known_id_names.add("apitoken_id")


        # Add to URL parameters from kwargs and skip the
        # ones that are in known_id_names
        for k, v in kwargs.items():

            if k in known_id_names:
                continue

            # Constructs the end of the URL from kwargs but
            # skips if a kwargs parameter is not a string
            if isinstance(v, str):
                url = urljoin(f'{url}/', v.lstrip("/"))

        # Remove the last '/' if in the URL as the call
        # won't work with it.
        url = url.rstrip('/')
        logger.info(f"URL to endpoint: {url}")

        return url

    def _params(self, **kwargs):
        """Parameters configurator for passing into requests as params attribute.

        Meant for parameters that get passed with the `params` attribute of
        requests.

        Parameters
        ----------
        **kwargs
            Keyword arguments containing params dict
        params : dict, optional
            A dict of keyword arguments that gets passed as params
            to the requests

        Returns
        -------
        dict
            The params dict of parameters to be passed with the request params attribute
        """
        logger.info("Calling _params()")
        logger.info(f"kwargs in: {kwargs}")

        params = {}

        if 'params' in kwargs:
            params = kwargs['params']

        logger.info(f"Returned params: {params}")

        return params

    def resource(self, method, jpayload=None, **kwargs):
        """Executes the HTTP request type defined with the method.

        This is the main function of the class, which does all the interfacing
        with the API. It can be called by its own with a valid HTTP method,
        but the preferred way is to define a resource method below that utilizes
        this one for interfacing. The difference between the 2 approaches is
        shown in the Examples or README file.

        Parameters
        ----------
        method : str
            Either GET or POST. Case insensitive.
        jpayload : dict, optional
            JSON formatted payload. Same as requests json sent with the body of
            the request.
        **kwargs
            These get passed to the _params() and _resource_url() methods, so read
            what is accepted there.

        Returns
        -------
        dict
            The JSON response with either the successful response or the error response.

        Raises
        ------
        MistAPIError
            When API call fails with status code >= 400
        """
        logger.info("Calling resource()")
        logger.debug(f'kwargs in: {kwargs}')

        # Get the params from the passed in kwargs
        params = self._params(**kwargs)

        # Build the full URL to the resource
        resource_url = self._resource_url(**kwargs)

        # Get the JSON response
        jresp = self._api_call(method, resource_url, params=params, json=jpayload)

        # Note: Logging level is no longer automatically reset to allow user control

        return jresp

    #
    ## Here are defined resource methods that interface with a specific endpoint.
    #

    def whoami(self, method='GET', **kwargs):
        """Resource method for manipulating '/self' endpoint.

        The URI inside the function is '/self' which gets
        added to the end of the URL.

        Parameters
        ----------
        method : str, default 'GET'
            A valid HTTP method, but only GET is allowed.
        **kwargs
            As defined with the _params() and _resource_url() methods

        Returns
        -------
        dict
            The JSON response from the resource() method
        """
        logger.info('Calling whoami()')
        logger.info(f'kwargs in: {kwargs}')

        kwargs['uri'] = '/self'

        return self.resource(method, **kwargs)

    def apitokens(self, method="GET", **kwargs):
        """Resource method for managing API tokens.

        The URI inside the function is '/self/apitokens' which gets
        added to the URL at the end.

        If run without any additional args it returns a list of all API tokens.
        If passing in the 'apitoken_id' method is DELETE and that id gets
        deleted.

        Parameters
        ----------
        method : str, default 'GET'
            A valid HTTP method.
            If kwargs contains 'apitoken_id', the method changes to DELETE.
        **kwargs
            As defined with the _params() and _resource_url() methods

        Returns
        -------
        dict
            The JSON response from the resource() method
        """
        logger.info('Calling apitokens()')
        logger.info(f'kwargs in: {kwargs}')

        # API tokens are under /self
        kwargs['uri'] = '/self/apitokens'

        # If we pass in the token ID the method
        # can only be DELETE
        if 'apitoken_id' in kwargs:
            method = "DELETE"

        return self.resource(method, **kwargs)

    def wlans(self, method='GET', jdata=None, **kwargs):
        """Resource method for manipulating '/wlans' endpoint.

        The URI inside the function is '/wlans' which gets
        added to the URL at the end

        Parameters
        ----------
        method : str, default 'GET'
            A valid HTTP method
        jdata : dict, optional
            JSON data payload for the request
        **kwargs
            As defined with the _params() and _resource_url() methods

        Returns
        -------
        dict
            The JSON response from the resource() method
        """
        logger.info('Calling wlans()')
        logger.info(f'kwargs in: {kwargs}')

        if not 'wlan_id' in kwargs:
            kwargs['uri'] = f'/wlans'

        return self.resource(method, jpayload=jdata, **kwargs)
