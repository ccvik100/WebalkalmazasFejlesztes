"""Static contract checks. DOES NOT compile .NET or claim running inference."""
from pathlib import Path
import json, re, unittest, xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PROJ = ROOT / 'MeetingNotesAPI'
CONTRACT = ROOT / 'tests' / 'omegaai_routes_v1_6.json'

class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.omega = {r['path'] for r in json.loads(CONTRACT.read_text(encoding='utf-8'))['routes']}
        cls.cs = '\n'.join(f.read_text(encoding='utf-8') for f in PROJ.glob('**/*.cs'))

    # TANANYAG – A csproj XML-ből ellenőrzi, hogy a célkeretrendszer net10.0 maradt.
    def test_target_framework(self):
        tree = ET.parse(PROJ / 'MeetingNotesAPI.csproj')
        self.assertEqual(tree.find('.//TargetFramework').text, 'net10.0')

    # TANANYAG – Ellenőrzi a fejlesztői profil nevét és 5200-as portját.
    def test_launch_profile(self):
        profiles=json.loads((PROJ/'Properties/launchSettings.json').read_text(encoding='utf-8'))['profiles']
        self.assertIn('MeetingNotesAPI - Visual Studio',profiles)
        self.assertEqual(profiles['MeetingNotesAPI - Visual Studio']['applicationUrl'],'http://localhost:5200')

    # TANANYAG – Összeveti az API által várt útvonalakat a dokumentált OmegaAI v1.6 szerződéssel.
    def test_omegaai_real_paths(self):
        paths=[
          '/health/live','/v1/health/ready','/v1/models','/v1/hardware','/v1/queue',
          '/v1/chat','/v1/chat/stream','/v1/summaries','/v1/summaries/stream',
          '/v1/audio/jobs','/v1/jobs/{job_id}',
          '/v1/jobs/{job_id}/events','/v1/jobs/{job_id}/cancel',
          '/v1/jobs/{job_id}/transcript','/v1/jobs/{job_id}/segments',
          '/v1/jobs/{job_id}/summary','/v1/jobs/{job_id}/speaker-names',
          '/v1/jobs/{job_id}/regenerate-summary',
          '/v1/tenants/{tenant_id}/persons','/v1/tenants/{tenant_id}/persons/{person_id}',
          '/v1/tenants/{tenant_id}/persons/{person_id}/samples',
          '/v1/tenants/{tenant_id}/enrollments/{enrollment_id}',
          '/v1/tenants/{tenant_id}/jobs/{job_id}/match',
          '/v1/tenants/{tenant_id}/jobs/{job_id}/approve'
        ]
        for path in paths:
            self.assertIn(path, self.omega, f'not part of OmegaAI v1.6: {path}')

    # TANANYAG – A tenant ne származzon a böngésző szabadon módosítható mezőjéből.
    def test_tenant_from_server_only(self):
        p=(PROJ/'Controllers/MeetingsController.cs').read_text(encoding='utf-8')
        self.assertIn('client.TenantId',p)
        self.assertNotIn('body.TenantId',p)
        self.assertIn('X-Tenant-Key',self.cs)
        self.assertIn('FixedTimeEquals',self.cs)

    # TANANYAG – Más alkalmazások munkáinak azonosítói nem jelenhetnek meg a /api/queue válaszában.
    def test_queue_does_not_expose_other_ids(self):
        gateway=(PROJ/'Infrastructure/OmegaAiGateway.cs').read_text(encoding='utf-8')
        block=gateway.split('public async Task<IResult> QueueStatusAsync')[1]
        self.assertNotIn('GetProperty("waiting_ids")', block)
        self.assertNotIn('waitingIds =', block)
        self.assertIn('waitingJobs', block)

    # TANANYAG – Az SSE működéséhez szükséges kulcsszavak/jelzések meglétét ellenőrzi.
    def test_stream_support(self):
        for key in ['ForwardSseAsync','FlushAsync','ResponseHeadersRead','text/event-stream','RequestAborted']:
            self.assertIn(key,self.cs)

    # TANANYAG – Megvizsgálja az X-Meeting-Key kulcsellenőrzés alapvető kódelemeit.
    def test_content_type_key_auth(self):
        p=(PROJ/'Infrastructure/ClientKeyMiddleware.cs').read_text(encoding='utf-8')
        self.assertIn('X-Meeting-Key',p)
        self.assertIn('401',p)
        self.assertIn('context.Items[ContextName]',p)

    # TANANYAG – Nem lehet éles kulcs vagy privát konfiguráció a ZIP-ben.
    def test_no_hardcoded_secrets(self):
        self.assertNotIn('0ec498bfc',self.cs)
        self.assertFalse((PROJ/'private/meetingnotes.secrets.json').exists())
        self.assertIn('CopyToPublishDirectory="Never"',(PROJ/'MeetingNotesAPI.csproj').read_text())

    # TANANYAG – Minden terjesztett JSON-fájlnak szabályosan értelmezhetőnek kell maradnia.
    def test_json(self):
        for p in PROJ.rglob('*.json'):
            json.loads(p.read_text(encoding='utf-8'))

    # TANANYAG – Megelőzi a korábbi CMD UTF-8 BOM miatti indítási hibát.
    def test_batch_ascii_no_bom(self):
        for p in (PROJ/'scripts').glob('*.bat'):
            b=p.read_bytes()
            self.assertFalse(b.startswith(b'\xef\xbb\xbf'),p.name)
            self.assertTrue(b.startswith(b'@echo off'),p.name)
            self.assertTrue(all(x<128 for x in b),p.name)

    # TANANYAG – Az ékezetes PowerShell 5.1 szkripteknek BOM-mal kell rendelkezniük.
    def test_ps_51_bom(self):
        for p in (PROJ/'scripts').glob('*.ps1'):
            self.assertTrue(p.read_bytes().startswith(b'\xef\xbb\xbf'),p.name)

    # TANANYAG – A védett vezérlőkben szerepelnie kell a kliens kulcsfejlécének.
    def test_swagger_endpoints_have_header(self):
        for p in (PROJ/'Controllers').glob('*.cs'):
            if p.name=='SystemController.cs': continue
            text=p.read_text(encoding='utf-8')
            self.assertIn('X-Meeting-Key',text,p.name)

if __name__=='__main__': unittest.main(verbosity=2)
