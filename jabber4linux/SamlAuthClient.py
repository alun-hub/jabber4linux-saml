#!/usr/bin/env python3

"""
SAML Authentication Client for Jabber4Linux
Handles SAML SSO authentication flow with Cisco CUCM and Keycloak IdP
"""

import requests
import json
import urllib.parse
from PyQt6 import QtWidgets, QtCore, QtWebEngineWidgets, QtWebEngineCore
from http.cookies import SimpleCookie


class SamlAuthClient:
    """
    Handles SAML SSO authentication flow for Cisco CUCM

    CUCM acts as Service Provider (SP) and redirects to Keycloak IdP.
    After successful authentication, CUCM provides session cookies that
    can be used for UDS API calls instead of Basic Auth.
    """

    def __init__(self, cucm_server, cucm_port='8443', debug=False):
        """
        Initialize SAML Auth Client

        Args:
            cucm_server: CUCM server hostname/IP
            cucm_port: CUCM HTTPS port (default 8443)
            debug: Enable debug output
        """
        self.cucm_server = cucm_server
        self.cucm_port = cucm_port
        self.debug = debug
        self.session_cookies = {}
        self.authenticated = False

        # CUCM SAML SSO endpoint
        self.saml_login_url = f'https://{cucm_server}:{cucm_port}/ssosp/saml/login'
        self.uds_base_url = f'https://{cucm_server}:{cucm_port}/cucm-uds'

    def get_saml_login_url(self):
        """Get the SAML login URL for CUCM"""
        return self.saml_login_url

    def is_authenticated(self):
        """Check if user is authenticated"""
        return self.authenticated

    def get_session_cookies(self):
        """Get session cookies for authenticated requests"""
        return self.session_cookies

    def set_session_cookies(self, cookies):
        """
        Set session cookies from browser

        Args:
            cookies: Dictionary of cookie name -> value pairs
        """
        self.session_cookies = cookies
        self.authenticated = len(cookies) > 0
        if self.debug:
            print(f":: SAML session cookies set: {list(cookies.keys())}")

    def clear_session(self):
        """Clear authentication session"""
        self.session_cookies = {}
        self.authenticated = False


class SamlLoginWindow(QtWidgets.QDialog):
    """
    SAML Login Window with embedded web browser

    Opens CUCM SAML login URL which redirects to Keycloak IdP.
    Captures session cookies after successful authentication.
    """

    # Signal emitted when authentication completes successfully
    authenticationCompleted = QtCore.pyqtSignal(dict)

    def __init__(self, saml_client, parent=None, *args, **kwargs):
        """
        Initialize SAML Login Window

        Args:
            saml_client: SamlAuthClient instance
            parent: Parent widget
        """
        super(SamlLoginWindow, self).__init__(parent, *args, **kwargs)
        self.saml_client = saml_client
        self.debug = saml_client.debug

        # Setup window
        self.setWindowTitle('SAML Login - Keycloak Authentication')
        self.resize(800, 600)

        # Create layout
        layout = QtWidgets.QVBoxLayout()

        # Info label
        self.lblInfo = QtWidgets.QLabel(
            'Please log in with your Keycloak credentials.\n'
            'The browser will redirect to your identity provider.'
        )
        self.lblInfo.setStyleSheet('padding: 10px; background-color: #e3f2fd;')
        layout.addWidget(self.lblInfo)

        # Create web engine view for SAML authentication
        self.browser = QtWebEngineWidgets.QWebEngineView()
        self.browser.setMinimumSize(780, 500)

        # Create custom web page to intercept cookies
        self.web_page = SamlWebPage(self)
        self.browser.setPage(self.web_page)

        # Monitor URL changes to detect successful authentication
        self.browser.urlChanged.connect(self.on_url_changed)
        self.browser.loadFinished.connect(self.on_load_finished)

        layout.addWidget(self.browser)

        # Button box
        self.buttonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self.buttonBox.rejected.connect(self.reject)
        layout.addWidget(self.buttonBox)

        self.setLayout(layout)

        # Load SAML login URL
        login_url = self.saml_client.get_saml_login_url()
        if self.debug:
            print(f":: Loading SAML login URL: {login_url}")
        self.browser.setUrl(QtCore.QUrl(login_url))

    def on_url_changed(self, url):
        """Handle URL changes during authentication flow"""
        url_string = url.toString()
        if self.debug:
            print(f":: URL changed: {url_string}")

        # Check if we've completed authentication and returned to CUCM
        if 'cucm-uds' in url_string or 'ssosp' in url_string:
            # We might be authenticated, check for cookies
            self.check_authentication()

    def on_load_finished(self, success):
        """Handle page load completion"""
        if self.debug:
            current_url = self.browser.url().toString()
            print(f":: Page load finished: {success}, URL: {current_url}")

        if success:
            # Check if authentication completed
            self.check_authentication()

    def check_authentication(self):
        """Check if authentication has completed by examining cookies"""
        # Get cookies from the browser
        profile = self.browser.page().profile()
        cookie_store = profile.cookieStore()

        # Request to extract all cookies
        # Note: Cookie extraction is asynchronous in PyQt6
        # We'll set up a cookie filter to capture them
        if not hasattr(self, '_cookie_check_done'):
            self._cookie_check_done = False
            QtCore.QTimer.singleShot(1500, self.extract_cookies)

    def extract_cookies(self):
        """Extract cookies from browser session"""
        # Use profile's cookie store to get all cookies
        profile = self.browser.page().profile()
        cookie_store = profile.cookieStore()

        # Connect cookie added signal
        cookie_store.cookieAdded.connect(self.on_cookie_received)

        # Alternative: Try to execute JavaScript to get cookies
        self.browser.page().runJavaScript(
            "document.cookie",
            self.on_javascript_cookies
        )

    def on_javascript_cookies(self, cookie_string):
        """Handle cookies received from JavaScript"""
        if not cookie_string:
            if self.debug:
                print(":: No cookies found yet")
            return

        if self.debug:
            print(f":: JavaScript cookies: {cookie_string}")

        # Parse cookie string
        cookies = {}
        cookie = SimpleCookie()
        cookie.load(cookie_string)

        for key, morsel in cookie.items():
            cookies[key] = morsel.value

        # Check for CUCM session cookies
        # Common CUCM cookie names: JSESSIONID, JSESSIONIDSSO, etc.
        if any(key.startswith('JSESSION') for key in cookies.keys()):
            if self.debug:
                print(f":: Found CUCM session cookies: {list(cookies.keys())}")
            self.complete_authentication(cookies)

    def on_cookie_received(self, cookie):
        """Handle individual cookie received from cookie store"""
        if self.debug:
            print(f":: Cookie received: {cookie.name().data().decode()}")

    def complete_authentication(self, cookies):
        """Complete authentication with received cookies"""
        if not cookies or hasattr(self, '_auth_completed'):
            return

        self._auth_completed = True
        self.saml_client.set_session_cookies(cookies)
        self.authenticationCompleted.emit(cookies)

        # Show success message
        self.lblInfo.setText('✓ Authentication successful! Closing window...')
        self.lblInfo.setStyleSheet('padding: 10px; background-color: #c8e6c9;')

        # Close dialog after short delay
        QtCore.QTimer.singleShot(1000, self.accept)


class SamlWebPage(QtWebEngineCore.QWebEnginePage):
    """
    Custom web page to intercept cookies and handle authentication
    """

    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window

        # Allow all SSL certificate errors for self-signed certs
        # In production, you should properly validate certificates
        self.loadFinished.connect(self.on_load_finished)

    def on_load_finished(self, success):
        """Handle page load completion"""
        if self.parent_window.debug:
            print(f":: SamlWebPage load finished: {success}")

    def certificateError(self, error):
        """Handle SSL certificate errors (accept self-signed certs)"""
        if self.parent_window.debug:
            print(f":: Certificate error ignored: {error.description()}")
        # Accept the certificate (use with caution!)
        return True


class SamlAuthenticatedSession:
    """
    HTTP Session wrapper that uses SAML cookies for authentication

    This replaces HTTP Basic Auth with session cookies obtained
    from SAML SSO authentication.
    """

    def __init__(self, saml_client, http_session=None):
        """
        Initialize authenticated session

        Args:
            saml_client: SamlAuthClient with valid session
            http_session: Optional requests.Session to use
        """
        self.saml_client = saml_client
        self.http_session = http_session or requests.Session()

        # Set cookies on session
        for name, value in saml_client.get_session_cookies().items():
            self.http_session.cookies.set(name, value)

    def get_session(self):
        """Get the authenticated HTTP session"""
        return self.http_session

    def update_cookies(self, new_cookies):
        """Update session cookies"""
        for name, value in new_cookies.items():
            self.http_session.cookies.set(name, value)
