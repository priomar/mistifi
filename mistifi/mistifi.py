import getpass
import sys
import json

import requests
from requests import Request, Session
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from urllib.parse import urljoin

import logging
import logzero
from logzero import logger


clouds = {
    "US": "api.mist.com",
    "EU": "api.eu.mist.com",
}

class MistiFi:
    '''All Mist API uris are found on https://api.mist.com/api/v1/docs/Home, and are accessible if logged in'''

    def __init__(self, cloud="us", token=None, username=None, password=None, user_token=None, apiv=1, verify=False, timeout=10):

        self.token = token
        self.username = username
        self.password = password
        self.user_token = user_token
        self.verify = bool(verify)
        self.timeout = abs(timeout)
        self.apiv = apiv
        self.csrftoken = None
        self.cloud = self._select_cloud(cloud)
        self.mist_base_api_url = f'https://{self.cloud}/'

        # Configure the session
        #self._config_session()

        '''
        #
        # If token provided, use it to log into the Mist cloud...
        #
        if token:
            self.token = token
            self.headers['Authorization'] = f'Token {self.token}'

        # ...otherwise prompt for user credentials if not provided
        else:
            #
            # If username not provided, ask for it
            #
            self.login_payload = {"email": None, "password": None}

            if not self.username:
                user_input = input("Mist username required. Should I use `{}` to continue [Y/n]?".format(getpass.getuser()))

                # Option for a user if they want to specify a username
                if user_input.lower() == "n":
                    #kwargs.update({ 'username': input("Username:\x20") })
                    self.username = input("Username:\x20")
                # ...any other answer, just use their current username
                else:
                    self.username = getpass.getuser()

            self.login_payload['email'] = self.username

            #
            # If password not provided, ask for it
            #
            if not self.password:
                #
                # If password was not provided, get it from user input
                self.password = getpass.getpass(f"Mist password for user `{self.username}` required:\x20".format(self.username))
            
            # Then set it in the login payload outside of conditional
            # as the password might have been passed in with the object
            self.login_payload['password'] = self.password

            # Finaly login
            self._user_login(self.login_payload)

        # Reset the log level to ERROR only
        logzero.loglevel(logging.ERROR)
        '''
    def comms(self):
        '''The first method to be called to configure the session and to login to the Mist cloud.

        It sets all the required headers.
        '''

        logger.info('Calling communicate()')

        logger.debug(f"Selected cloud: '{self.cloud}' >> '{cloud.upper()}'")
        logger.debug(f'Base URL: {self.mist_base_api_url}')

        # Configure the session
        self._config_session()

        #
        # If token provided, use it to log into the Mist cloud...
        #
        if self.token:
            self.headers['Authorization'] = f'Token {self.token}'
            logger.debug('Proceeding with the token.')

        # ...otherwise prompt for user credentials if not provided
        else:
            #
            # If username not provided, ask for it
            #
            self.login_payload = {"email": None, "password": None}

            if not self.username:
                user_input = input("Mist username required. Should I use `{}` to continue [Y/n]?".format(getpass.getuser()))

                # Option for a user if they want to specify a username
                if user_input.lower() == "n":
                    #kwargs.update({ 'username': input("Username:\x20") })
                    self.username = input("Username:\x20")
                # ...any other answer, just use their current username
                else:
                    self.username = getpass.getuser()

            self.login_payload['email'] = self.username

            #
            # If password not provided, ask for it
            #
            if not self.password:
                #
                # If password was not provided, get it from user input
                self.password = getpass.getpass(f"Mist password for user `{self.username}` required:\x20".format(self.username))
            
            # Then set it in the login payload outside of conditional
            # as the password might have been passed in with the object
            self.login_payload['password'] = self.password
            logger.debug('Proceeding with username and password.')

            # Finaly login
            self._user_login(self.login_payload)

        # Reset the log level to ERROR only
        logzero.loglevel(logging.ERROR)

    def logout(self):
        '''Logs out of the cloud, which is not really 
        needed, but avialable anyaway.

        Returns
        -------
        The HTTP JSON response
        '''
        logger.info("Calling logout()")

        url_logout = self._resource_url(uri="/logout")
        resp = self._api_call("POST", url_logout)

        logging.debug(f'Logout response: {resp}')

        # Reset logging to ERROR as this method is called through _api_call and 
        # is not reset as if it were with by calling resource
        logzero.loglevel(logging.ERROR)

        return resp

    def _config_session(self):
        '''Session configurator for headers and requests.Session()
        '''

        logger.info(f'Calling _config_session()')

        # Setup base headers
        self.headers = {
            'Content-Type': 'application/json',
            'Accept' : 'application/json',
        }

        logger.debug(f'Updated Headers: {self.headers}')

        self.session = requests.Session() 

        # Setup the retry strategy
        # https://findwork.dev/blog/advanced-usage-python-requests-timeouts-retries-hooks/
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        self.session.mount(self.mist_base_api_url, HTTPAdapter(max_retries=retries))
        
        # Handle response status
        #assert_status_hook = lambda response, *args, **kwargs: response.raise_for_status()
        #self.session.hooks["response"] = [assert_status_hook]

    def _select_cloud(self, cloud):
        '''Cloud selector, which either selects the specified 'cloud' or returns the default 'US' one.

        Params
        ------
        cloud: `str`
            Can be 'us' or 'eu', or 'EU'
        '''
        logger.info("Calling _select_cloud()")

        try:
            return clouds[cloud.upper()]
        except KeyError:
            logging.exception(f'Not a valid entry {list(clouds.keys())}. Using "US" as default.')
            return clouds["US"]

    def _user_login(self, login_payload):
        '''Method to authenticate with username/password credentials. 

        Params:
        ------- 
        login_payload: dict
            A dict with username and password credentials
        
        Return:
        -------
        Nothing
        '''
        logger.info(f'Calling _user_login()')
        
        url_login = self._resource_url(uri='/login')
        #url_login = self._resource_url(org_id=':org_id')
        #url_login = self._resource_url(site_id=':site_id')
        #url_login = self._resource_url(site_id=':site_id', uri='/uri')
        #url_login = self._resource_url(org_id=":org_id", site_id=':site_id', uri='/uri')
        #url_login = self._resource_url(org_id=":org_id/orgA/", site_id=':site_id/siteA', uri='/uri')
        #url_login = self._resource_url(org_id="/:org_id/orgA/", site_id=':site_id/siteA', uri='/uri')
        #url_login = self._resource_url(somthing='/:sdkinvite_id/email',site_id=':site_id', uri='/uri')
        #url_login = self._resource_url(collection='/:collection',object_id=':obj_id',site_id=':site_id')
        #url_login = self._resource_url(somthing='/:sdkinvite_id/email',org_id=':org_id', uri='/uri')
        #url_login = self._resource_url(somthing='/:sdkinvite_id/email',org_id=":org_id", site_id=':site_id', uri='/uri')
        #url_login = self._resource_url(somthing='/:sdkinvite_id/email', blah="/blah", org_id=":org_id", site_id=':site_id', uri='/uri')
        #exit(0)

        # Login with or without the 2 factor token
        resp = self.session.post(url_login, json=login_payload)

        # The headers and cookies in the response
        resp_head = resp.headers
        resp_csrftoken = resp.cookies['csrftoken']

        logger.info(f'Login response code: {resp.status_code}')
        logger.debug(f'Response HEAD: {resp_head}')
        
        # Need to update the headers with the CSRF token to be able
        # to POST, PUT or DELETE in further requests
        try:
            self.session.headers['X-CSRFTOKEN'] = resp_csrftoken
        except KeyError:
            logger.exception("'Set-Cookie' not in headder response")
            return

        logger.debug(f'Session headders should include X-CSRFTOKEN token: {self.session.headers}')

    def _api_call(self, method, url, **kwargs):
        '''The API call handler.

        This method is used by `resource()`. kwargs passed in get passed to the 
        requests.session instance

        Params
        ------
        method: `str`
            A valid HTTP method

        url: `str`
            URL with the endpoint included

        **kwargs: 
        These are passed into the requests and include the `params` and `json` 
        attributes which are the exact same ones as used by requests.

        Returns:
        --------
        The full response in JSON format including `_global_result` AND
        The error if status string returned is not 0, else `None`.
        '''
        logger.info("Calling _api_call()")
        logger.info(f"Method is: {method.upper()}")
        logger.info(f"Calling URL: {url}")
        logger.debug(f'With headers: {self.headers}')

        # This is where the call hapens
        response = getattr(self.session, method.lower())(url, **kwargs)
        resp_head = response.headers
        jresponse = response.json()
        resp_status_code = response.status_code

        logger.info(f"Response status code: {resp_status_code}")
        logger.debug(f'The response: {jresponse}')

        # Return nothing if status code is higher than 400
        # And return the response text, which usually has 
        # the reson for the failure.
        if resp_status_code >= 400:
            logger.error(f"Response Error:\n{jresponse}")
            return None
        
        return jresponse

    def _resource_url(self, **kwargs):
        '''The resource URL formatter
        
        Will return the propperly formated url with any provided org_id, site_id, uri or parameters, or a
        combination of all

        Args
        ----
        org_id: `str`
            The Organisation ID
        site_id: `str`
            The Site ID
        uri: `str`
            The endpoint resource, e.g. '/self', or 'self', or '/self/'
        params: dict
            Parameters that get added to the request. These get handled by the params of requests.
        
        Returns
        -------
        The full URL string to the requested endpoint
        '''
        logger.info("Calling _resource_url()")
        logger.info(f"kwargs in: {kwargs}")
        
        url = f"{self.mist_base_api_url}/api/v{self.apiv}/"

        # Set of above parameters that will be skipped by the
        # for loop below so as to not add them again to the URL
        known_id_names = set()

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
        if 'uri' in kwargs:
            url = urljoin(url, kwargs['uri'].strip('/'))# + "/"
            known_id_names.add("uri")

        # 'params' are special nd are passed to requests as params
        # So to no not be preocessed here, they are put into 
        # known id names
        known_id_names.add("params")

        # Add to URL parameters from kwargs and skip the 
        # ones that are in known_id_names
        for k, v in kwargs.items():
            
            if k in known_id_names:
                continue
            
            # Constructs the end of the URL from kwargs but
            # skips if a kwargs parameter is not a string
            if isinstance(v, str):
                url = urljoin(f'{url}/', v.lstrip("/"))

        # Remove the last '/' if in the url as the call
        # won't work with it.
        if url[-1] == "/":
            url = url[:-1]

        logger.debug(f"URL to endpoint: {url}")

        return url

    def _params(self, **kwargs):

        logger.info("Calling _params()")
        logger.info(f"kwargs in: {kwargs}")

        params = {}

        if 'params' in kwargs:
            params = kwargs['params']

        logger.debug(f"Returned params: {params}")

        return params

    def resource(self, method, jpayload=None, **kwargs):

        logger.info("Calling resource()")
        logger.debug(f'kwargs in: {kwargs}')
        
        # Get the params from the passed in kwargs
        params = self._params(**kwargs)

        # Build the full URL to the resource
        resource_url = self._resource_url(**kwargs)

        # Get the JSON response
        jresp = self._api_call(method, resource_url, params=params, json=jpayload)
        
        # Reset logging to ERROR
        logzero.loglevel(logging.ERROR)

        return jresp

    def whoami(self, method='GET', **kwargs):

        logger.info('Calling whoami()')
        logger.info(f'kwargs in: {kwargs}')

        kwargs['uri'] = f'/self'

        return self.resource(method, **kwargs)

    def wlans(self, method='GET', data=None, **kwargs):
        #   /api/v1/sites/:site_id/wlans
        #   /api/v1/sites/:site_id/wlans/:wlan_id/
        #   /api/v1/sites/:site_id/wlans/:wlan_id/parameter << POST, DELETE, PUT
        #   /api/v1/sites/:site_id/wlans/derived
        #   /api/v1/sites/:site_id/wlans/derived?resolve=false

        logger.info('Calling wlans()')
        logger.info(f'kwargs in: {kwargs}')

        if not 'wlan_id' in kwargs:
            kwargs['uri'] = f'/wlans'

        return self.resource(method, jpayload=data, **kwargs)



