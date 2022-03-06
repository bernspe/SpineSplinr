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

gen = DocumentGenerator()
verify='/Volumes/1TB/Users/peterbernstein/cert/skoliosekinder_de.pem'
base_url = 'http://localhost:8000/'
#base_url = 'https://api.skoliosekinder.de/'
NUMBER_OF_CAREGIVERS=7
NUMBER_OF_PHYSICIANS=2


def create_caseroom(token,members=None):
    response=requests.post(base_url+'cr/caseroom/',json={'title': gen.word(), 'members':members}, headers={'authorization': 'Bearer ' + token}, verify=verify)
    status = response.status_code
    if ((status==200) | (status==201)):
        assert True
        cr=json.loads(response.content)
        cr_id=cr['id']
        print('New CR ID: ',cr_id)
        return cr
    else:
        assert False

def create_consent_for_caseroom(token, caseroom, consent, members=None):
    response=requests.post(base_url+'consent/',json={'consent_content': consent, 'involved_users':members, 'referring_Caseroom':caseroom['id']}, headers={'authorization': 'Bearer ' + token}, verify=verify)
    status = response.status_code
    if ((status==200) | (status==201)):
        assert True
    else:
        assert False

def create_consented_caseroom(token, consent, members=None):
    cr=create_caseroom(token,members=members)
    create_consent_for_caseroom(token,cr, consent, members=members)
    return cr

@pytest.fixture
def caserooms(dataset, consent, request):
    """
    This fixture will create caserooms, one for each Caregiver. If non_consented is set, no P3-consent is attached to the caseroom
    :param dataset:
    :param consent:
    :param request:
    :return:
    """
    marker = request.node.get_closest_marker("non_consented")
    caregivers=dataset[dataset['role']=='Caregiver']
    physicians=dataset[(dataset['role']!='Caregiver') & (dataset['role']!='Child')]
    if consent and not marker:
        s=caregivers.apply(lambda x: create_consented_caseroom(x.token, consent,members=[random.choice(x.children),str(physicians.sample().username.values[0])]), axis=1)
    else:
        s = caregivers.apply(lambda x: create_caseroom(x.token, members=[random.choice(x.children), str(physicians.sample().username.values[0])]), axis=1)
    df=pd.DataFrame(s.to_list())
    return df

def send_cr_msg(token, sender, caseroom, faulty=False):
    """

    :param token:
    :param sender:
    :param caseroom:
    :param faulty: if True will send messages from not CR-Member
    :return:
    """
    msg=gen.sentence()
    response=requests.post(base_url+'cr/caseroomentry/', json={'caseroom':caseroom, 'sender':sender, 'text':msg}, headers={'authorization': 'Bearer ' + token}, verify=verify)
    status = response.status_code
    if ((status == 200) | (status == 201)):
        assert not faulty
        cr = json.loads(response.content)
        cr_id = cr['id']
        print('New CR MSG ID: ', cr_id)
        return cr
    else:
        assert faulty

def setUserMsg(u,msg, cr,df):
    df.loc[u,'msg']=msg
    df.loc[u,'caseroom']=cr

@pytest.fixture
def send_cr_messages(caserooms, dataset, request):
    """
    this Fixture will allocate msgs to various caserooms. If faulty_users is set, msgs will come from users that dont belong to the caseroom
    :param caserooms:
    :param dataset:
    :param request:
    :return:
    """
    marker = request.node.get_closest_marker("faulty_users")
    allusers = dataset['username'].to_list()
    users=dataset.set_index('username')
    caserooms['possible_senders']  = caserooms.apply(lambda x: x.members+[x.owner], axis=1)
    if marker:
        caserooms['sender'] = caserooms['possible_senders'].apply(lambda x: getRandomFaultyUser(x, allusers))
    else:
        caserooms['sender']=caserooms['possible_senders'].apply(lambda x: random.choice(x))
    caserooms['token']=caserooms['sender'].apply(lambda x: users.loc[x].token)
    s=caserooms.apply(lambda x: send_cr_msg(x.token,x.sender,x.id, faulty=marker is not None),axis=1)
    if marker:
        return any(s.to_list()) # look if there were could be sent any msgs (which we don't expect)
    msgs = pd.DataFrame(s.to_list())
    msgs.set_index('caseroom', inplace=True)
    caserooms.set_index('id', inplace=True)
    msgs.to_pickle('splineapp/tests/crmsgs.pkl')
    caserooms.to_pickle('splineapp/tests/cr.pkl')
    #set the msgs to the users who should have received/sent one
    res=msgs.join(caserooms,rsuffix='cr')
    res['caseroom']=res.index
    res.apply(lambda x: setUserMsg(x.possible_senders,x.text, x.caseroom,users),axis=1)
    users.to_pickle('splineapp/tests/users.pkl')
    return users

def getRandomFaultyUser(eligUsers,allUsers):
    fusers=[item for item in allUsers if item not in eligUsers]
    return random.choice(fusers)

def getCrIDsForUser(token):
    response=requests.get(base_url+'cr/caseroom/listbyparticipant/', headers={'authorization': 'Bearer ' + token}, verify=verify)
    status = response.status_code
    if ((status == 200) | (status == 201)):
        assert True
        res=json.loads(response.content)
        cr = [c['id'] for c in res]
        return cr
    else:
        assert False

def getCrMsgsFromNotConsentedCaseroom(cr, token):
    if (not pd.isnull(cr)):
        response = requests.get(base_url + 'cr/caseroomentry/?caseroom='+cr, headers={'authorization': 'Bearer ' + token}, verify=verify)
        status = response.status_code
        if ((status == 200) | (status == 201)):
            assert False
        else:
            assert True

def getCrMsgs(cr, token):
    if (not pd.isnull(cr)):
        response = requests.get(base_url + 'cr/caseroomentry/?caseroom='+cr, headers={'authorization': 'Bearer ' + token}, verify=verify)
        status = response.status_code
        if ((status == 200) | (status == 201)):
            assert True
            msg = json.loads(response.content)
            return msg[0]['text']
        else:
            assert False

class TestCaseRooms:
    def test_make_P3consent(self,consent):
        """
        This tests the functionality of the consent fixture to provide a dummy P3 consent
        :param consent:
        :return:
        """
        assert ((len(consent)>0) & (type(consent)==str))


    def test_create_users(self,valid_users):
        """
        Asserting the creation of the valid_users, which is the number of Caregivers + number of physicians
        :param valid_users:
        :return:
        """
        assert NUMBER_OF_PHYSICIANS+NUMBER_OF_CAREGIVERS==len(valid_users)

    def test_make_caregivers(self,make_Caregivers):
        """
        Asserting the creation of the correct number of caregivers
        :param make_Caregivers:
        :return:
        """
        assert NUMBER_OF_CAREGIVERS==len(make_Caregivers)

    def test_dataset(self,dataset):
        n_children=len(dataset[dataset['role']=='Child'])
        print('Our dataset contains of %i children'%n_children)
        assert len(dataset)==NUMBER_OF_CAREGIVERS+NUMBER_OF_PHYSICIANS+n_children

    def test_caserooms(self,caserooms):
        """
        will check that each caregiver owns a created caseroom
        :param caserooms:
        :return:
        """
        assert len(caserooms)==NUMBER_OF_CAREGIVERS

    def test_check_sent_msgs(self,consent,send_cr_messages):
        """
        CR Message delivery integrity test 1
        This test will create CR Messages and will look at every CR that those msgs were delivered and did not spill into caserooms of other users
        :param consent:
        :param send_cr_messages:
        :return:
        """
        df=send_cr_messages
        df['username']=df.index
        df['val_caserooms']=df.apply(lambda x: getCrIDsForUser(x.token), axis=1)
        df['val_msgs']=df.apply(lambda x: getCrMsgs(x.caseroom, x.token), axis=1)
        df.to_pickle('splineapp/tests/cr_msg_validation.pkl')
        assert (df['msg'].dropna()==df['val_msgs'].dropna()).all()

    @pytest.mark.faulty_users
    def test_check_sent_msgs_from_faulty_users(self,consent,send_cr_messages):
        """
        CR Message delivery integrity test 1
        This test will create CR Messages and will look at every CR that those msgs were delivered and did not spill into caserooms of other users
        :param consent:
        :param send_cr_messages:
        :return:
        """
        assert not send_cr_messages


    @pytest.mark.non_consented
    def test_check_sent_msgs_but_deny_because_of_missing_consent(self,send_cr_messages):
        """
        This test expects a failure of accessing the CR-Messages, because there hasn't been given any consent by the caregiver
        :param send_cr_messages:
        :return:
        """
        df = send_cr_messages
        df['username'] = df.index
        df['val_caserooms'] = df.apply(lambda x: getCrIDsForUser(x.token), axis=1)
        df.apply(lambda x: getCrMsgsFromNotConsentedCaseroom(x.caseroom, x.token), axis=1)

