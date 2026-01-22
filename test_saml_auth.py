#!/usr/bin/env python3
"""
SAML Authentication Test Script for Jabber4Linux

This script helps debug SAML SSO authentication issues by testing
each step of the authentication flow independently.

Usage:
    python3 test_saml_auth.py --server cucm.example.com --port 8443
    python3 test_saml_auth.py --server cucm.example.com --debug
"""

import sys
import argparse
import requests
import urllib.parse
from PyQt6 import QtWidgets, QtCore

# Add jabber4linux to path
sys.path.insert(0, '/home/user/jabber4linux')

from jabber4linux.SamlAuthClient import SamlAuthClient, SamlLoginWindow


def test_connectivity(server, port):
    """Test 1: Basic HTTPS connectivity to server"""
    print("\n" + "="*60)
    print("TEST 1: Basic HTTPS Connectivity")
    print("="*60)

    url = f"https://{server}:{port}/"
    print(f"Testing connection to: {url}")

    try:
        response = requests.get(url, timeout=10, verify=False)
        print(f"✓ Connection successful!")
        print(f"  Status code: {response.status_code}")
        print(f"  Server responded: YES")
        return True
    except requests.exceptions.SSLError as e:
        print(f"✗ SSL Error: {e}")
        print("  Solution: Add server certificate to ~/.config/jabber4linux/server-certs/")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"✗ Connection Error: {e}")
        print("  Solution: Check server address and port, verify firewall rules")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_saml_endpoint(server, port):
    """Test 2: SAML SSO endpoint availability"""
    print("\n" + "="*60)
    print("TEST 2: SAML SSO Endpoint")
    print("="*60)

    saml_url = f"https://{server}:{port}/ssosp/saml/login"
    print(f"Testing SAML endpoint: {saml_url}")

    try:
        response = requests.get(saml_url, timeout=10, verify=False, allow_redirects=False)
        print(f"✓ SAML endpoint accessible!")
        print(f"  Status code: {response.status_code}")

        if response.status_code == 302 or response.status_code == 301:
            redirect_url = response.headers.get('Location', 'N/A')
            print(f"  Redirect to: {redirect_url}")
            if 'keycloak' in redirect_url.lower() or 'auth' in redirect_url.lower():
                print("  ✓ Detected IdP redirect (Keycloak/SAML)")
            else:
                print(f"  ⚠ Unexpected redirect target: {redirect_url}")
        elif response.status_code == 200:
            print("  ⚠ No redirect - SAML might not be configured")
            print("  Solution: Enable SAML SSO on CUCM")

        return True
    except Exception as e:
        print(f"✗ Error accessing SAML endpoint: {e}")
        print("  Solution: Verify CUCM SAML SSO is enabled")
        return False


def test_uds_api(server, port):
    """Test 3: UDS API availability"""
    print("\n" + "="*60)
    print("TEST 3: UDS API Endpoint")
    print("="*60)

    uds_url = f"https://{server}:{port}/cucm-uds/version"
    print(f"Testing UDS API: {uds_url}")

    try:
        response = requests.get(uds_url, timeout=10, verify=False)
        print(f"✓ UDS API accessible!")
        print(f"  Status code: {response.status_code}")
        print(f"  Response preview: {response.text[:200]}...")
        return True
    except Exception as e:
        print(f"✗ Error accessing UDS API: {e}")
        print("  Solution: Verify CUCM is running and UDS service is enabled")
        return False


def test_dns_discovery():
    """Test 4: DNS Service Discovery"""
    print("\n" + "="*60)
    print("TEST 4: DNS Service Discovery")
    print("="*60)

    try:
        from dns import resolver, rdatatype

        # Test CUCM direct discovery
        print("Testing _cisco-uds._tcp DNS SRV record...")
        try:
            res = resolver.resolve(qname='_cisco-uds._tcp', rdtype=rdatatype.SRV, lifetime=5, search=True)
            for srv in res.rrset:
                print(f"  ✓ Found CUCM: {srv.target} port {srv.port}")
        except Exception as e:
            print(f"  ✗ Not found: {e}")

        # Test Expressway discovery
        print("Testing _collab-edge._tls DNS SRV record...")
        try:
            res = resolver.resolve(qname='_collab-edge._tls', rdtype=rdatatype.SRV, lifetime=5, search=True)
            for srv in res.rrset:
                print(f"  ✓ Found Expressway: {srv.target} port {srv.port}")
        except Exception as e:
            print(f"  ✗ Not found: {e}")

        print("\n  Note: DNS discovery is optional. Manual server entry works too.")
        return True
    except ImportError:
        print("  ⚠ dnspython not installed - DNS discovery unavailable")
        print("    Install: pip install dnspython")
        return False


def test_saml_interactive(server, port, debug=False):
    """Test 5: Interactive SAML authentication test"""
    print("\n" + "="*60)
    print("TEST 5: Interactive SAML Authentication")
    print("="*60)
    print("This will open a browser window for SAML login.")
    print("Watch the console for detailed cookie and redirect information.")
    print("")

    # Create Qt application
    app = QtWidgets.QApplication(sys.argv)

    # Create SAML client
    saml_client = SamlAuthClient(server, port, debug=True)

    print(f"SAML Login URL: {saml_client.get_saml_login_url()}")
    print("")
    print("Opening browser window...")
    print("=" * 60)

    # Create and show SAML login window
    window = SamlLoginWindow(saml_client)

    def on_auth_completed(cookies):
        print("\n" + "="*60)
        print("✓ AUTHENTICATION COMPLETED!")
        print("="*60)
        print(f"Cookies received: {len(cookies)}")
        for name, value in cookies.items():
            if name.startswith('JSESSION'):
                print(f"  ✓ {name}: {value[:20]}...")
            else:
                print(f"    {name}: {value[:20]}...")

        print("\nYou can now close the browser window.")

    window.authenticationCompleted.connect(on_auth_completed)

    result = window.exec()

    if result == QtWidgets.QDialog.DialogCode.Accepted:
        print("\n✓ SAML authentication successful!")
        print(f"Session cookies: {list(saml_client.get_session_cookies().keys())}")
        return True
    else:
        print("\n✗ SAML authentication cancelled or failed")
        return False


def run_all_tests(server, port, debug=False, interactive=False):
    """Run all tests"""
    print("\n" + "="*60)
    print("JABBER4LINUX SAML AUTHENTICATION TEST SUITE")
    print("="*60)
    print(f"Server: {server}")
    print(f"Port: {port}")
    print(f"Debug: {debug}")
    print("="*60)

    results = []

    # Run connectivity tests
    results.append(("Connectivity", test_connectivity(server, port)))
    results.append(("SAML Endpoint", test_saml_endpoint(server, port)))
    results.append(("UDS API", test_uds_api(server, port)))
    results.append(("DNS Discovery", test_dns_discovery()))

    # Run interactive test if requested
    if interactive:
        results.append(("Interactive SAML", test_saml_interactive(server, port, debug)))

    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print("="*60)
    print(f"Passed: {passed}/{total}")
    print("="*60)

    if passed == total:
        print("\n🎉 All tests passed! SAML authentication should work.")
    else:
        print("\n⚠ Some tests failed. Review the output above for solutions.")


def main():
    parser = argparse.ArgumentParser(
        description='Test SAML authentication for Jabber4Linux',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic test
  python3 test_saml_auth.py --server cucm.example.com

  # Test with Expressway
  python3 test_saml_auth.py --server expressway-e.example.com --port 8443

  # Full test with interactive SAML login
  python3 test_saml_auth.py --server cucm.example.com --interactive

  # Debug mode
  python3 test_saml_auth.py --server cucm.example.com --debug --interactive
        """
    )

    parser.add_argument('--server', required=True, help='CUCM or Expressway server hostname')
    parser.add_argument('--port', default='8443', help='HTTPS port (default: 8443)')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    parser.add_argument('--interactive', action='store_true', help='Run interactive SAML login test')
    parser.add_argument('--test', choices=['connectivity', 'saml', 'uds', 'dns', 'interactive'],
                        help='Run specific test only')

    args = parser.parse_args()

    # Disable SSL warnings for testing
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    if args.test:
        # Run specific test
        if args.test == 'connectivity':
            test_connectivity(args.server, args.port)
        elif args.test == 'saml':
            test_saml_endpoint(args.server, args.port)
        elif args.test == 'uds':
            test_uds_api(args.server, args.port)
        elif args.test == 'dns':
            test_dns_discovery()
        elif args.test == 'interactive':
            app = QtWidgets.QApplication(sys.argv)
            test_saml_interactive(args.server, args.port, args.debug)
    else:
        # Run all tests
        run_all_tests(args.server, args.port, args.debug, args.interactive)


if __name__ == '__main__':
    main()
