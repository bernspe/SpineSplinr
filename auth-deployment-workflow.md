# OAuth Deployment Workflow
## /admin/
### Django OAuth Toolkit &rarr; New Application
- Client ID und Client Secret generieren lassen
- Authorization grant type = Resource owner password-based
- Client type = confidential
- diese werden dann im 
    - .env File des Backends (CLIENT_ID, CLIENT_SECRET)
    - .env File des Frontends (VUE_APP_CLIENT_ID, VUE_APP_CLIENT_SECRET) eingepflegt

## Google
### Registrierung bei Google
https://console.developers.google.com/projectselector/apis/credentials?pli=1&supportedpurview=project&project=&folder=&organizationId=

Die Redirect URI muss genau auf das Frontend zielen.
### Backend .env File
- GOOGLE_OAUTH2_KEY (=Client-ID)
- GOOGLE_OAUTH2_SECRET (=Schlüssel)
### Frontend .env File
- VUE_APP_SOCIAL_AUTH_GOOGLE_ID (=Client-ID)