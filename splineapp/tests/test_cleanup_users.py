import requests
import pandas as pd

verify='/Volumes/1TB/Users/peterbernstein/cert/skoliosekinder_de.pem'
base_url = 'http://localhost:8000/'

def delete_user(username, token):
    requests.delete(base_url + 'users/' + username + '/', headers={'authorization': 'Bearer ' + token},
                    verify=verify)

def test_cleanup():
    df=pd.read_pickle('users.pkl')
    df.apply(lambda x: delete_user(x['username'],x['token']), axis=1)
