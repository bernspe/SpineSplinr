import random

import pytest
from random import randint
import requests
import names
import uuid
import json
import pandas as pd
from essential_generators import DocumentGenerator
from environs import Env
env = Env()
env.read_env()

# set this to true if you want to run frontend tests afterwards where you need the users
# users will be stored in the users.json file
# remember to unset it to false afterwards as otherwise the db will be trashed with fake users
KEEP_USERS=True

gen = DocumentGenerator()
verify='/Volumes/1TB/Users/peterbernstein/cert/skoliosekinder_de.pem'
CLIENT_ID = env('CLIENT_ID')
CLIENT_SECRET = env('CLIENT_SECRET')


@pytest.fixture(scope='module')
def userroles(request,existing_staff_user):
    base_url = getattr(request.module, "base_url", 'http://localhost:8000/')
    response = requests.get(base_url + 'userrole/', headers={'authorization': 'Bearer ' + existing_staff_user}, verify=verify)
    assert response.status_code == 200
    if response.status_code == 200:
        d = json.loads(response.content)
        return d

@pytest.fixture(scope='module')
def existing_staff_user(request):
    e=env('EMAIL_ACCOUNT_NAME')
    p=env('GEN_STAFF_USER_PASSWORD')
    base_url = getattr(request.module, "base_url", 'http://localhost:8000/')
    response = requests.post(base_url + 'o/emailtoken/', data={'email':e,'password':p,'client_id':CLIENT_ID,'client_secret':CLIENT_SECRET,'grant_type':'password','scope':'write'}, verify=verify)
    d = json.loads(response.content)
    assert response.status_code == 200
    if response.status_code == 200:
        token = d['access_token']
        return token

@pytest.fixture(scope='module')
def validated_staff_user(existing_staff_user, request):
    u = env('GEN_STAFF_USER_USERNAME')
    base_url = getattr(request.module, "base_url", 'http://localhost:8000/')
    response = requests.get(base_url + 'userinfo/', headers={'authorization': 'Bearer ' + existing_staff_user}, verify=verify)
    assert response.status_code == 200
    d = json.loads(response.content)
    assert d['username'] == u
    if response.status_code == 200:
        return {'username':d['username'],'token':existing_staff_user}

@pytest.fixture(scope='module')
def consent(validated_staff_user, request):
    cons=[]
    base_url = getattr(request.module, "base_url", 'http://localhost:8000/')
    ctoken=validated_staff_user['token']
    def _consentP3document():
        if (len(cons)==0):
            f = open("splineapp/tests/p3dummy.md", "rb")
            file = {'document': f}
            response = requests.post(base_url + 'consentcontent/', data={'consent_type': 'P3'}, files=file,
                                     headers={'authorization': 'Bearer ' + ctoken}, verify=verify)
            status = response.status_code
            if ((status==200) | (status==201)):
                assert True
                consent_id2 = json.loads(response.content)['id']
                cons.append(consent_id2)
                return consent_id2
            else:
                assert False

    yield _consentP3document()
    for c in cons:
        requests.delete(base_url+'consentcontent/'+c+'/',headers={'authorization': 'Bearer ' + ctoken}, verify=verify)

def password_maker():
    import string
    import secrets

    symbols = ['*', '%', '£']  # Can add more

    password = ""
    for _ in range(5):
        password += secrets.choice(string.ascii_lowercase)
    password += secrets.choice(string.ascii_uppercase)
    password += secrets.choice(string.digits)
    password += secrets.choice(symbols)
    return password

def name_generator(n=1):
    for i in range(n):
        firstName = names.get_first_name()
        lastName = names.get_last_name()
        username=str(uuid.uuid4())
        password=password_maker()
        email=firstName.lower()+ str(randint(10, 90)) + '@skoliosekinder.de'
        data = {'client_id':CLIENT_ID,'client_secret':CLIENT_SECRET,'grant_type':'password','scope':'write',
                'email': email,'password': password, 'first_name': firstName,'last_name': lastName,'username': username}
        yield data

def children_generator():
    n=randint(1,4)
    for i in range(n):
        firstName = names.get_first_name()
        lastName = names.get_last_name()
        email=firstName.lower()+ str(randint(10, 90)) + '@skoliosekinder.de'
        username = str(uuid.uuid4())
        data = {'first_name': firstName,'last_name': lastName, 'date_of_birth': '2010-10-01','email':email,'username': username, 'password':'startpass'}
        yield data



@pytest.fixture(scope='class')
def user_account(request):
    """
    tries to register a new user
    :return: user token and user data from name_generator
    """
    user_data=[]
    base_url = getattr(request.module, "base_url", 'http://localhost:8000/')
    def _user_account(data):
        response = requests.post(base_url + 'register/', data=data, verify=verify)
        print(response.content)
        d=json.loads(response.content)
        assert response.status_code==200
        if response.status_code==200:
            token = d['access_token']
            record= {'token':token, **data}
            user_data.append(record)
            return record, response.status_code

    yield _user_account
    if not KEEP_USERS:
        for d in user_data:
            requests.delete(base_url + 'users/' + d['username'] + '/', headers={'authorization': 'Bearer ' + d['token']}, verify=verify)


@pytest.fixture(scope='class')
def child_account(request):
    user_data=[]
    base_url = getattr(request.module, "base_url", 'http://localhost:8000/')
    def _child_account(parent,child):
        response = requests.post(base_url + 'users/' + parent['username'] + '/addchild/', json=child,
                                 headers={'authorization': 'Bearer ' + parent['token']}, verify=verify)
        assert response.status_code==200
        if response.status_code==200:
            login = requests.post(base_url+'o/emailtoken/',data={**child,'client_id':CLIENT_ID,'client_secret':CLIENT_SECRET,'grant_type':'password','scope':'write'}, verify=verify)
            assert login.status_code==200
            if login.status_code==200:
                l=json.loads(login.content)
                token = l['access_token']
                record= {'token':token, **child}
                user_data.append(record)
                return record, login.status_code

    yield _child_account
    if not KEEP_USERS:
        for d in user_data:
            requests.delete(base_url + 'users/' + d['username'] + '/', headers={'authorization': 'Bearer ' + d['token']}, verify=verify)


def checktoken(token, base_url):
    response=requests.get(base_url+'userinfo/', headers={'authorization': 'Bearer ' + token}, verify=verify)
    assert response.status_code==200

def updateUser(username,token,data, base_url):
    response = requests.patch(base_url + 'users/'+username+'/', data=data, headers={'authorization': 'Bearer ' + token}, verify=verify)
    return response.status_code == 200

@pytest.fixture(scope='class')
def valid_users(user_account, request):
    users=[]
    NUMBER_OF_CAREGIVERS = getattr(request.module, "NUMBER_OF_CAREGIVERS", 3)
    NUMBER_OF_PHYSICIANS = getattr(request.module, "NUMBER_OF_PHYSICIANS", 3)
    base_url = getattr(request.module, "base_url", 'http://localhost:8000/')
    for n in name_generator(n=NUMBER_OF_CAREGIVERS+NUMBER_OF_PHYSICIANS):
        user,status=user_account(n)
        assert status==200
        checktoken(user['token'], base_url)
        users.append(user)
    return users

@pytest.fixture(scope='class')
def make_Caregivers(valid_users, request):
    parents=[]
    NUMBER_OF_CAREGIVERS = getattr(request.module, "NUMBER_OF_CAREGIVERS", 3)
    base_url = getattr(request.module, "base_url", 'http://localhost:8000/')
    for user in valid_users[0:NUMBER_OF_CAREGIVERS]:
        accomplished = updateUser(user['username'],user['token'],{'roles':['Caregiver']}, base_url)
        assert accomplished
        if accomplished:
            parents.append(user)
    return parents

@pytest.fixture(scope='class')
def make_Physicians(valid_users, request):
    physicians=[]
    NUMBER_OF_CAREGIVERS = getattr(request.module, "NUMBER_OF_CAREGIVERS", 3)
    NUMBER_OF_PHYSICIANS = getattr(request.module, "NUMBER_OF_PHYSICIANS", 3)
    base_url = getattr(request.module, "base_url", 'http://localhost:8000/')
    for user in valid_users[NUMBER_OF_CAREGIVERS:(NUMBER_OF_CAREGIVERS+NUMBER_OF_PHYSICIANS)]:
        role=random.choice(['Physician','Pediatric','Specialist','Orthopaedic'])
        accomplished = updateUser(user['username'],user['token'],{'roles':[role]}, base_url)
        assert accomplished
        if accomplished:
            physicians.append({**user,'role':role})
    return physicians

@pytest.fixture(scope='class')
def dataset(make_Caregivers,child_account, make_Physicians):
    users=[]
    for parent in make_Caregivers:
        children=[]
        for c in children_generator():
            child,status=child_account(parent,c)
            accomplished = status==200
            assert accomplished
            if accomplished:
                children.append(c['username'])
                users.append({**child,'role':'Child'})
        users.append({**parent,'children':children,'role':'Caregiver'})
    df=pd.DataFrame(users+make_Physicians)
    df.to_pickle('splineapp/tests/users.pkl')
    df.drop(columns=['client_id','client_secret','grant_type','scope']).to_json('splineapp/tests/users.json', orient='records')
    return df