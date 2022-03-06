#CaseRoom Workflow
##The idea
Patient or Caregiver of patient can open a caseroom where a content-based discussion of patient data can be done in a Messenger-like fashion.
##Steps
###1. Create new CaseRoom
This is only allowed for patient/caregiver.
- URL: POST /cr/caseroom/
- provide Auth Token in Header &#8594; gives the caseroom-owner
- Body: "members": ['Physician1','Specialist',...]
- returns caseroom id
- yields a websocket message to /ws/splineapp/user/username/ 
 -     message = {
        'caseroom':str(instance.id),
        'caseroom_owner': str(instance.owner),
        'caseroom_members': instance.get_members_str(),
        'status': 'created'}
- after that a new websocket connection to /ws/caseroom/**caseroom** (where caseroom is the id retrieved from the message) should be opened by frontend
###2. Retrieve Caserooms of a specific user
- GET /cr/caseroom/listbyowner/
- provide Auth Token in Header &#8594; gives the user in question
###3. Retrieve Caseroom entries
- URL: GET /cr/caseroomentry/
- provide Auth Token in Header
- Query params: "caseroom": id
###4. Get specific Caseroom
- URL: GET /cr/caseroomentry/
- provide Auth Token in Header
###5. Eliminate NewsTag for requesting user in caseroom
- eliminates the requesting user from the news-tag in this caseroom
- URL: PATCH /cr/caseroomentry/CASEROOM-UUID/eliminate_news_tag/
- provide Auth Token in Header
###6. Post new Caseroom entry
- URL: POST /cr/caseroomentry/
- provide Auth Token in Header &#8594; gives the entry-sender
- Body: "caseroom": id, "text": message
- yields a websocket message to /ws/caseroom/**caseroom** (where caseroom is the id written in body)
###7. Retrieve a specific entry
- URL: /cr/caseroomentry/UUID/
- provide Auth Token in Header
