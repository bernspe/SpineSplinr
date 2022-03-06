import pytest
from random import randint
import requests
import json


from splineapp.tests.conftest import name_generator

verify='/Volumes/1TB/Users/peterbernstein/cert/skoliosekinder_de.pem'
base_url = 'http://localhost:8000/'
#base_url = 'https://api.skoliosekinder.de/'
NUMBER_OF_CAREGIVERS=5
NUMBER_OF_PHYSICIANS=3

class TestLogin:
    def test_login_staff_user(self,validated_staff_user):
        """
        Checks if the Staff user specified in .env file is existent in the api
        :param validated_staff_user: fixature, checking loginability of the staff user
        :return:
        """
        print('Checking the Staff User')
        print(validated_staff_user)
        assert validated_staff_user

    def test_login_users(self,valid_users):
        """
        Checks if the newly created users (that consist of the planned number of Caregivers and Physicians) could be logged in
        :param valid_users:
        :return:
        """
        assert len(valid_users)==NUMBER_OF_CAREGIVERS+NUMBER_OF_PHYSICIANS


    def test_userrole_list2_staff_user(self, validated_staff_user):
        """
        Checks if Staff users are presented the full list of Userrole possibilities
        :param validated_staff_user
        :return:
        """
        data_collection=[{},{'ignoreage':True,'language':'de'},{'ignoreage':True,'language':'de','format':'list-all'}]
        if validated_staff_user:
            for data in data_collection:
                print('Probing %s' % str(data))
                response = requests.post(base_url + 'userrole/list2/', data=data, headers={'authorization': 'Bearer ' + validated_staff_user['token']},verify=verify)
                assert response.status_code == 200
                if response.status_code == 200:
                    d = json.loads(response.content)
                    cats=[item['category'] for item in d]
                    assert "Staff" in cats
                    assert "Med" in cats
                    assert "Caregiver" in cats
                    assert "Adult" in cats
        else:
            assert False

     
    def test_userrole_list2_normal_user(self, dataset):
        """
        Checks if regular users are presented the full list of Userrole possibilities, except the staff roles
        :param dataset of randomly created users including children
        :return:
        """
        child_data=dataset[dataset['role']=='Child']
        adult_data=dataset[dataset['role']!='Child']
        uc = child_data.iloc[randint(0, len(child_data) - 1)]
        ua = adult_data.iloc[randint(0, len(adult_data) - 1)]
        users=[(uc,'Child'),(ua,'Adult')]
        data_collection=[{},{'ignoreage':False,'language':'de'},{'ignoreage':False,'language':'de','format':'list-users'}]
        for (u,typ) in users:
            if u.any():
                for data in data_collection:
                    print('Probing %s: %s'%(typ,str(data)))
                    response = requests.post(base_url + 'userrole/list2/', data=data, headers={'authorization': 'Bearer ' + u['token']},verify=verify)
                    assert response.status_code == 200
                    if response.status_code == 200:
                        d = json.loads(response.content)
                        cats=[item['category'] for item in d]
                        assert not ("Staff" in cats)
                        if (typ=='Child'):
                            assert not ("Med" in cats)
                            assert not ("Caregiver" in cats)
                            assert "Child" in cats
                            assert not ("Adult" in cats)
                        else:
                            assert ("Med" in cats)
                            assert ("Caregiver" in cats)
                            assert ("Adult" in cats)

            else:
                assert False


     
    def test_missing_consents(self,dataset, userroles):
        """
        Checks that for the new added users the required consents are marked as missing
        :param dataset including children, caregivers, physicians; userroles list
        :return:
        """
        rdict={r['role']:r['consents'] for r in userroles}
        for i in range(len(dataset)):
            u=dataset.iloc[i]
            response = requests.get(base_url + 'users/'+u['username']+'/getmissingconsents/', headers={'authorization': 'Bearer ' + u['token']}, verify=verify)
            status = response.status_code
            if ((status == 200) | (status == 201)):
                d = json.loads(response.content)
                ur=rdict[u['role']]
                if ur:
                    ul=ur.split(',')
                    ul=[l.strip() for l in ul]
                    assert sorted(ul)==sorted(d)
            else:
                assert False

     
    def test_missing_proofs(self,dataset, userroles):
        """
        Checks that for the new added users the required proofs are marked as missing
        :param dataset including children, caregivers, physicians; userroles list
        :return:
        """
        rdict={r['role']:r['proof'] for r in userroles}
        for i in range(len(dataset)):
            u=dataset.iloc[i]
            response = requests.get(base_url + 'users/'+u['username']+'/getmissingproofs/', headers={'authorization': 'Bearer ' + u['token']}, verify=verify)
            status = response.status_code
            if ((status == 200) | (status == 201)):
                d = json.loads(response.content)
                ur=rdict[u['role']]
                if ur:
                    ul=ur.split(',')
                    ul=[l.strip() for l in ul]
                    assert sorted(ul)==sorted(d)
            else:
                assert False

     
    def test_lookup_med_users(self, dataset):
        """
        Checks if the Med-User Lookup from the database includes all the medical users which had been currently added to our randomly generated dataset
        :param dataset:
        :return:
        """
        u=dataset.iloc[randint(0,len(dataset)-1)]
        response = requests.get(base_url + 'users/getmedusers/',headers={'authorization': 'Bearer ' + u['token']}, verify=verify)
        status = response.status_code
        if ((status == 200) | (status == 201)):
            d = json.loads(response.content)
            username_list= [el['username'] for el in d]
            df_med=dataset[dataset['role'].isin(['Physician','Pediatric','Specialist','Orthopaedic'])]
            df_nomed=dataset[~dataset['role'].isin(['Physician','Pediatric','Specialist','Orthopaedic'])]
            # Check if all the new meds are in the list
            assert df_med['username'].apply(lambda x: x in username_list).all()
            # Check that none of the other no-med users is in the med-list
            assert not df_nomed['username'].apply(lambda x: x in username_list).any()
        else:
            assert False

     
    def test_get_dependent_children(self, dataset):
        """
        Checks, if all the dependent children of a certain caregiver can be retrieved
        :param dataset:
        :return:
        """
        caregiver_data = dataset[dataset['role'] == 'Caregiver']
        u = caregiver_data.iloc[randint(0, len(caregiver_data) - 1)]
        response = requests.get(base_url + 'getdependentchildren/',headers={'authorization': 'Bearer ' + u['token']}, verify=verify)
        status = response.status_code
        if ((status == 200) | (status == 201)):
            d = json.loads(response.content)
            username_list = [el['username'] for el in d]
            children=dataset[dataset['role'] == 'Child']
            # check if the returned children are a subpopulation of the ones who were randomly created
            assert children['username'].apply(lambda x: x in username_list).any()
            # Check if the returned children are truely the own ones
            assert set(username_list)==set(u['children'])
        else:
            assert False

     
    def test_getcaregiver(self, dataset):
        """
        Checks, if all the caregiver of a selected child can be found
        :param dataset:
        :return:
        """
        children_data = dataset[dataset['role'] == 'Child']
        u = children_data.iloc[randint(0, len(children_data) - 1)]
        response = requests.get(base_url + 'getcaregiver/',headers={'authorization': 'Bearer ' + u['token']}, verify=verify)
        status = response.status_code
        if ((status == 200) | (status == 201)):
            d = json.loads(response.content)
            username_list = [el['username'] for el in d]
            caregiver=dataset[dataset['role'] == 'Caregiver']
            # check if the returned caregiver is part of the population
            assert caregiver['username'].apply(lambda x: x in username_list).any()
            # check if the requesting child truly belongs to the caregiver
            uc=caregiver[caregiver['username'].isin(username_list)]
            assert uc['children'].apply(lambda x: u['username'] in x).any()
        else:
            assert False

     
    def test_get_minProfileFromCurrentlyInvitedUser(self,dataset):
        """
        Checks if the endpoint returns the information about the currently added user
        :param dataset:
        :return:
        """
        u=dataset.iloc[randint(0,len(dataset)-1)]
        response = requests.post(base_url + 'getminprofilefromcurrentlyinviteduser/', data={'username': u['username']}, verify=verify)
        status = response.status_code
        if ((status == 200) | (status == 201)):
            d = json.loads(response.content)
            assert d['username']==u['username']
        else:
            assert False

     
    def test_add_caregivers_to_specific_child(self, dataset):
        """
        tests, if a physician can add a caregiver user to a specified child user
        :param dataset:
        :return:
        """
        df_med = dataset[dataset['role'].isin(['Physician', 'Pediatric', 'Specialist', 'Orthopaedic'])]
        u_med = df_med.iloc[randint(0, len(df_med) - 1)]
        children_data = dataset[dataset['role'] == 'Child']
        u_child = children_data.iloc[randint(0, len(children_data) - 1)]
        caregiver_data = dataset[dataset['role'] == 'Caregiver']
        # exclude the caregivers where this child is already assigned to
        caregiver_data=caregiver_data[caregiver_data['children'].apply(lambda x: u_child['username'] not in x)]
        u_care_new = caregiver_data.iloc[randint(0, len(caregiver_data) - 1)]

        if (len(u_child)>0):
            data={'child_username': u_child['username'], 'caregiver_usernames':[u_care_new['username']]}
            response = requests.post(base_url + 'users/add_caregivers_to_specific_child/',
                                     json=data,headers={'authorization': 'Bearer ' + u_med['token']}, verify=verify)
            status = response.status_code
            if ((status == 200) | (status == 201)):
                d = json.loads(response.content)
                for user in d:
                    assert (user['username']==u_care_new['username']) | (user['username']==u_child['username'])
            else:
                assert False
        else:
            assert False

    @pytest.fixture(scope='class')
    def deactivated_user(self,dataset):
        u = dataset.iloc[randint(0, len(dataset) - 1)]
        response = requests.post(base_url + 'users/'+u['username']+'/toggleUserActivation/', headers={'authorization': 'Bearer ' + u['token']},
                                verify=verify)
        status = response.status_code
        if ((status == 200) | (status == 201)):
            assert True
            d = json.loads(response.content)
            assert d['user-activation']=='False'
            return u
        else:
            assert False

     
    def test_reactivate_deactivated_user(self,deactivated_user):
        """
        checks if a formerly deactivated user can be reset active properly
        :param deactivated_user:
        :return:
        """
        response = requests.get(base_url + 'register/activate/'+deactivated_user['username']+'/',
                                verify=verify)
        status = response.status_code
        assert ((status == 200) | (status == 201))

     
    def test_invite_new_user_via_qrcode(self,dataset):
        """
        checks if the backend methods for inviting a user via qr code are working
        :param dataset:
        :return:
        """
        u = dataset.iloc[randint(0, len(dataset) - 1)]
        data={}
        for rn in name_generator():
            data={'first_name':rn['first_name'], 'last_name':rn['last_name'],'email':rn['email'],'username':rn['username']}
        response = requests.post(base_url + 'invite_via_qrcode/', json=data, headers={'authorization': 'Bearer ' + u['token'], 'Content-Type': 'application/json'},
                                verify=verify)
        status = response.status_code
        if ((status == 200) | (status == 201)):
            d = json.loads(response.content)
            img_url=base_url[:-1] + d['login_qrcode']
            img_response= requests.get(img_url, headers={'authorization': 'Bearer ' + u['token']},verify=verify)
            if img_response.status_code==200:
                # decode the qrcode
                # i = Image.open(StringIO(img_response.content))
                # output = pyzbar.decode(i)
                assert True
            else:
                assert False
        else:
            assert False

     
    def test_invite_new_user_via_email(self,dataset):
        """
        checks if the backend methods for inviting a user via email are working
        :param dataset:
        :return:
        """
        u = dataset.iloc[randint(0, len(dataset) - 1)]
        data={}
        for rn in name_generator():
            data={'first_name':rn['first_name'], 'last_name':rn['last_name'],'email':rn['email'],'username':rn['username']}
        response = requests.post(base_url + 'invite_via_email/', json=data, headers={'authorization': 'Bearer ' + u['token'], 'Content-Type': 'application/json'},
                                verify=verify)
        status = response.status_code
        assert status==200


    def test_invite_new_user_via_pdf(self, dataset):
        """
        checks if the backend methods for inviting a user via pdf are working
        :param dataset:
        :return:
        """
        u = dataset.iloc[randint(0, len(dataset) - 1)]
        data = {}
        for rn in name_generator():
            data = {'first_name': rn['first_name'], 'last_name': rn['last_name'], 'email': rn['email'],
                    'username': rn['username']}
        response = requests.post(base_url + 'invite_via_pdf/', json=data,
                                 headers={'authorization': 'Bearer ' + u['token'], 'Content-Type': 'application/json'},
                                 verify=verify)
        status = response.status_code
        assert status == 200
        
    def test_forgot_password(self, dataset):
        """
        checks if the backend methods for inviting a user via pdf are working
        :param dataset:
        :return:
        """
        u = dataset.iloc[randint(0, len(dataset) - 1)]
        response = requests.get(base_url + 'forgotpassword/email/?email='+u['email'],
                                 headers={'authorization': 'Bearer ' + u['token']},
                                 verify=verify)
        status = response.status_code
        if ((status == 200) | (status == 201)):
            d = json.loads(response.content)
            assert d['username']==u['username']
        else:
            assert False



            
    

