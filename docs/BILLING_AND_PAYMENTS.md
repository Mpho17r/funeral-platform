# LINDA Subscription Billing

## Payment flow

LINDA uses PayFast hosted checkout. Card details are entered on PayFast; LINDA does not collect or store card numbers.

1. The business selects its plan at registration.
2. The seven-day trial starts after the owner verifies their email address.
3. At trial expiry, business API access is restricted but the workspace data is retained.
4. An authorised business owner opens Subscription, where LINDA calculates the amount from the selected plan, staff and branch usage.
5. LINDA creates a pending payment and redirects the customer to PayFast hosted checkout.
6. The browser return URL is informational only. LINDA activates the subscription only after a signed ITN has passed PayFast's server-to-server validation and the merchant, payment reference and gross amount checks.

The first integration supports one-off monthly payments. A verified payment grants access through the end of that calendar month; the platform then requires the next month's payment before access continues. Automatic recurring collections are intentionally not enabled yet because the monthly amount changes with the business's peak staff and branch usage. Recurring card subscriptions/tokenisation need a separate design for variable usage, plan changes, retries and cancellation.

## Required backend environment

Set these only in the deployment secret store or ignored backend .env file. Never commit real values:

- PAYFAST_MERCHANT_ID
- PAYFAST_MERCHANT_KEY
- PAYFAST_PASSPHRASE
- PAYFAST_SANDBOX=true for sandbox; set false only after live merchant approval and end-to-end tests.
- PUBLIC_API_URL must be the public HTTPS API base URL that can receive /subscription/payfast/itn.
- PUBLIC_APP_URL must be the public HTTPS LINDA frontend URL.

PayFast sandbox and live checkout/ITN validation hosts are selected by PAYFAST_SANDBOX.

## Before enabling live payments

- Complete PayFast merchant onboarding and configure the passphrase.
- Configure sandbox credentials in a non-production test environment.
- Apply the platform-payments migration only after the feature branch is reviewed and approved.
- Test successful, cancelled, duplicate, wrong-amount, wrong-merchant and invalid-signature ITNs.
- Confirm PayFast's server-to-server validation endpoint is reachable from the API host.
- Confirm the business becomes active only after a valid ITN; never trust the browser return URL.
- Review VAT registration and invoicing requirements with an accountant before collecting customer subscription payments.

No production credentials, migrations or deployment are included in this feature branch.
