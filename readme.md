# The scoliosis detection backend: SpineSplinr

## Architecture
Micro-Service Architecture that consists of the following parts:
 - Django-Rest-Framework running with postgres-DB
 - Authentication: OAuth2_provider for proprietary authentication and Auth0-Integration for social login
 - Celery worker to run time-consuming ML algorithms
 - Django channels for websocket-based chatroom communication
 - ML Model Manager Module for sort of hub-based execution of plug-in machine learning models

## Testing
All tests had been done with pytest. 

## Deployment
The backend is deployed with docker-compose.

