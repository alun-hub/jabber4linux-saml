#!/usr/bin/env python3

"""
SAML Authentication Client for Jabber4Linux
Handles SAML SSO authentication flow with Cisco CUCM and Keycloak IdP
"""

from PyQt6 import QtWidgets, QtCore, QtWebEngineWidgets, QtWebEngineCore
from http.cookies import SimpleCookie

# Injected into every page in the browser session.
# Intercepts SAML assertion form submissions and extracts the NameID (username)
# by decoding the SAMLResponse field and parsing the XML.
# Uses console.log with a sentinel prefix so Python can capture it via
# javaScriptConsoleMessage without any extra IPC mechanism.
_SAML_USERNAME_SCRIPT = """
(function() {
    function extractSamlUsername(form) {
        try {
            var samlInput = form.querySelector('input[name="SAMLResponse"]');
            if (!samlInput) return;
            var xml = atob(samlInput.value);
            var doc = (new DOMParser()).parseFromString(xml, 'text/xml');
            var ns = 'urn:oasis:names:tc:SAML:2.0:assertion';
            var nodes = doc.getElementsByTagNameNS(ns, 'NameID');
            if (nodes.length > 0 && nodes[0].textContent) {
                console.log('SAML_USERNAME:' + nodes[0].textContent.trim());
            }
        } catch(e) {}
    }
    var orig = HTMLFormElement.prototype.submit;
    HTMLFormElement.prototype.submit = function() {
        extractSamlUsername(this);
        orig.apply(this, arguments);
    };
    document.addEventListener('submit', function(e) { extractSamlUsername(e.target); }, true);
})();
"""


class SamlAuthClient:
    """
    Handles SAML SSO authentication flow for Cisco CUCM

    CUCM acts as Service Provider (SP) and redirects to Keycloak IdP.
    After successful authentication, CUCM provides session cookies that
    can be used for UDS API calls instead of Basic Auth.

    Supports both:
    - Direct CUCM connection (internal)
    - Expressway-C/E proxy (external/MRA)
    """

    def __init__(self, cucm_server, cucm_port='8443', debug=False, use_expressway=False):
        """
        Initialize SAML Auth Client

        Args:
            cucm_server: CUCM/Expressway server hostname/IP
            cucm_port: HTTPS port (default 8443, or 443 for Expressway)
            debug: Enable debug output
            use_expressway: True if connecting via Expressway-C proxy
        """
        self.cucm_server = cucm_server
        self.cucm_port = cucm_port
        self.debug = debug
        self.use_expressway = use_expressway
        self.session_cookies = {}
        self.authenticated = False
        self.username = None

        # CUCM/Expressway SAML SSO endpoint
        # Expressway proxies /ssosp and /cucm-uds to CUCM
        self.saml_login_url = f'https://{cucm_server}:{cucm_port}/ssosp/saml/login'
        self.uds_base_url = f'https://{cucm_server}:{cucm_port}/cucm-uds'

        if self.debug:
            if use_expressway:
                print(f':: SAML client configured for Expressway-C proxy: {cucm_server}:{cucm_port}')
            else:
                print(f':: SAML client configured for direct CUCM: {cucm_server}:{cucm_port}')

    def get_saml_login_url(self):
        """Get the SAML login URL for CUCM"""
        return self.saml_login_url

    def get_username(self):
        """Get username extracted from SAML assertion"""
        return self.username

    def set_username(self, username):
        """Set username parsed from SAML NameID"""
        # NameID may be email format (user@domain) — use only the local part
        self.username = username.split('@')[0] if '@' in username else username
        if self.debug:
            print(f':: SAML username set from assertion: {self.username}')

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
        self.collected_cookies = {}
        self.cucm_session_cookies = {}
        self._auth_completed = False

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

        # Set up cookie store to capture cookies
        profile = self.browser.page().profile()
        self.cookie_store = profile.cookieStore()
        self.cookie_store.cookieAdded.connect(self.on_cookie_added)

        # Inject script that extracts NameID from SAML assertion form submission.
        # Runs at document creation so it wraps form.submit() before Keycloak calls it.
        if not profile.scripts().find('saml_username_extractor'):
            script = QtWebEngineCore.QWebEngineScript()
            script.setName('saml_username_extractor')
            script.setSourceCode(_SAML_USERNAME_SCRIPT)
            script.setInjectionPoint(QtWebEngineCore.QWebEngineScript.InjectionPoint.DocumentCreation)
            script.setWorldId(QtWebEngineCore.QWebEngineScript.ScriptWorldId.MainWorld)
            profile.scripts().insert(script)

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

    def on_cookie_added(self, cookie):
        """Handle cookie added by the web engine"""
        cookie_name = cookie.name().data().decode('utf-8')
        cookie_value = cookie.value().data().decode('utf-8')
        cookie_domain = cookie.domain().lstrip('.')

        if self.debug:
            print(f":: Cookie received: {cookie_name} (domain: {cookie_domain})")

        # Store all cookies
        self.collected_cookies[cookie_name] = cookie_value

        # Track JSESSION cookies only from the CUCM/Expressway domain.
        # Use boundary-aware matching: cookie domain must either be exactly the
        # server hostname, or a parent domain (e.g. "company.com" for "expressway.company.com").
        if cookie_name.startswith('JSESSION'):
            cucm_server = self.saml_client.cucm_server
            domain_match = (
                cookie_domain == cucm_server or
                cucm_server.endswith('.' + cookie_domain)
            )
            if domain_match:
                self.cucm_session_cookies[cookie_name] = cookie_value
                if self.debug:
                    print(f":: Found CUCM session cookie: {cookie_name} from {cookie_domain}")

    def on_url_changed(self, url):
        """Handle URL changes during authentication flow"""
        url_string = url.toString()
        if self.debug:
            print(f":: URL changed: {url_string}")

        # Check if we've completed authentication and returned to CUCM
        if 'cucm-uds' in url_string or ('ssosp' in url_string and 'login' not in url_string):
            # We might be authenticated, check for cookies
            if self.debug:
                print(':: Detected CUCM redirect - checking authentication')
            QtCore.QTimer.singleShot(2000, self.check_authentication)

    def on_load_finished(self, success):
        """Handle page load completion"""
        current_url = self.browser.url().toString()

        if self.debug:
            print(f":: Page load finished: {success}, URL: {current_url}")
            print(f":: Current cookies collected: {list(self.collected_cookies.keys())}")

        if not success:
            if self.debug:
                print(f":: Page load failed for: {current_url}")
            # Don't fail completely - might be a redirect
            return

        # Only check authentication when we're back on the CUCM/Expressway server,
        # not on the IdP (Keycloak) pages where the IdP may set its own JSESSION cookies
        if self.saml_client.cucm_server in current_url:
            QtCore.QTimer.singleShot(1000, self.check_authentication)

    def check_authentication(self):
        """Check if authentication has completed by examining cookies"""
        if self._auth_completed:
            return

        if self.debug:
            print(f":: Checking authentication... Collected cookies: {list(self.collected_cookies.keys())}")
            print(f":: CUCM domain cookies: {list(self.cucm_session_cookies.keys())}")

        # Prioritize cookies confirmed to be from the CUCM/Expressway domain
        if self.cucm_session_cookies:
            if self.debug:
                print(f":: Found CUCM session cookies: {list(self.cucm_session_cookies.keys())}")
            self.complete_authentication(self.collected_cookies)
        else:
            # Try JavaScript cookie extraction as fallback
            if self.debug:
                print(":: No CUCM cookies from cookieStore yet, trying JavaScript...")
            self.browser.page().runJavaScript(
                "document.cookie",
                self.on_javascript_cookies
            )

    def on_javascript_cookies(self, cookie_string):
        """Handle cookies received from JavaScript"""
        if self._auth_completed:
            return

        if not cookie_string:
            if self.debug:
                print(":: No cookies from JavaScript yet")
            # Schedule another check
            QtCore.QTimer.singleShot(1000, self.check_authentication)
            return

        if self.debug:
            print(f":: JavaScript cookies: {cookie_string}")

        # Parse cookie string
        cookies = {}
        cookie = SimpleCookie()
        try:
            cookie.load(cookie_string)
            for key, morsel in cookie.items():
                cookies[key] = morsel.value
        except Exception as e:
            if self.debug:
                print(f":: Error parsing cookies: {e}")
            # Try simple split
            for item in cookie_string.split(';'):
                if '=' in item:
                    key, value = item.strip().split('=', 1)
                    cookies[key] = value

        # Merge with collected cookies
        self.collected_cookies.update(cookies)

        # Check for CUCM session cookies
        if any(key.startswith('JSESSION') for key in cookies.keys()):
            if self.debug:
                print(f":: Found CUCM session cookies via JavaScript: {list(cookies.keys())}")
            self.complete_authentication(self.collected_cookies)
        else:
            if self.debug:
                print(f":: Still waiting for JSESSION cookies. Have: {list(cookies.keys())}")
            # Schedule another check
            QtCore.QTimer.singleShot(1500, self.check_authentication)

    def complete_authentication(self, cookies):
        """Complete authentication with received cookies"""
        if self._auth_completed:
            return

        if not cookies:
            if self.debug:
                print(":: complete_authentication called but no cookies provided")
            return

        # Filter for relevant CUCM cookies
        cucm_cookies = {k: v for k, v in cookies.items() if k.startswith('JSESSION')}

        if not cucm_cookies:
            if self.debug:
                print(f":: No JSESSION cookies found. Available: {list(cookies.keys())}")
            # Schedule another check
            QtCore.QTimer.singleShot(2000, self.check_authentication)
            return

        self._auth_completed = True
        # Pass only domain-verified CUCM cookies to the session.
        # Fall back to the JSESSION-filtered collected cookies (JS fallback path).
        session_cookies = self.cucm_session_cookies if self.cucm_session_cookies else cucm_cookies
        self.saml_client.set_session_cookies(session_cookies)
        self.authenticationCompleted.emit(session_cookies)

        # Show success message
        self.lblInfo.setText(f'✓ Authentication successful! Found cookies: {", ".join(cucm_cookies.keys())}\nClosing window...')
        self.lblInfo.setStyleSheet('padding: 10px; background-color: #c8e6c9;')

        if self.debug:
            print(f":: Authentication complete with {len(cucm_cookies)} CUCM cookies")

        # Close dialog after short delay
        QtCore.QTimer.singleShot(1500, self.accept)


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

    def javaScriptConsoleMessage(self, level, message, line, source):
        """Capture SAML username logged by the injected script"""
        if message.startswith('SAML_USERNAME:'):
            username = message[14:].strip()
            if username:
                self.parent_window.saml_client.set_username(username)

    def certificateError(self, error):
        """Handle SSL certificate errors (accept self-signed certs)"""
        if self.parent_window.debug:
            print(f":: Certificate error ignored: {error.description()}")
        # Accept the certificate (use with caution!)
        return True

