from copy import deepcopy
import unittest
from fastapi.testclient import TestClient
from klone.main import create_app
from klone.council72 import demo_proposal


class CouncilApiTests(unittest.TestCase):
    def setUp(self):self.client=TestClient(create_app())

    def test_catalog_and_view_route(self):
        result=self.client.get('/api/cognition/council72/catalog')
        self.assertEqual(result.status_code,200)
        self.assertEqual(len(result.json()['members']),72)
        self.assertFalse(result.json()['authority']['permission_changes'])
        page=self.client.get('/council72')
        self.assertEqual(page.status_code,200)
        self.assertIn('lang="fi"',page.text)

    def test_same_request_replays_and_does_not_grant_authority(self):
        a=self.client.post('/api/cognition/council72/simulate',json=demo_proposal())
        b=self.client.post('/api/cognition/council72/simulate',json=demo_proposal())
        self.assertEqual(a.status_code,200)
        self.assertEqual(a.json(),b.json())
        self.assertTrue(a.json()['replay_matches'])
        self.assertFalse(a.json()['binding_authority'])

    def test_api_rejects_unbounded_extra_or_nonfinite_claims(self):
        for changes in ({'goal':'x'*2001},{'deployment_approval':True},{'signals':{'risk':'NaN'}},
                        {'signals':{'risk':True}},{'ring_evidence':{'9':['unknown']}},
                        {'ring_evidence':{'1':['x']*9}},{'founder_votes':{'9':'endorse'}}):
            proposal={**demo_proposal(),**changes}
            self.assertEqual(self.client.post('/api/cognition/council72/simulate',json=proposal).status_code,422)

    def test_draft_endpoint_only_builds_unsent_draft(self):
        request={'proposal':demo_proposal(),'king_id':9,'courier_id':27,'channel':'forum','message':'Tarkistettava luonnos'}
        response=self.client.post('/api/cognition/council72/draft',json=request)
        self.assertEqual(response.status_code,200)
        self.assertFalse(response.json()['delivery_enabled'])
        for changes in ({'courier_id':24},{'king_id':24},{'king_id':True},{'channel':'other'},{'destination':'https://example.com'}):
            self.assertEqual(self.client.post('/api/cognition/council72/draft',json={**request,**changes}).status_code,422)
        for classification in ('restricted','sealed'):
            proposal={**demo_proposal(),'classification':classification}
            self.assertEqual(self.client.post('/api/cognition/council72/draft',json={**request,'proposal':proposal}).status_code,403)


if __name__=='__main__':unittest.main()
