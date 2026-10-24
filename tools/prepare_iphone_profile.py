"""Publish only this teaching host's public CA in an iPhone installation profile.

Installing and trusting it is always a manual action on the user's iPhone.
No MDM enrollment, private key, account or device-management payload is included.
"""
from pathlib import Path
import plistlib,uuid
from cryptography import x509
from cryptography.hazmat.primitives import serialization,hashes

ROOT=Path(__file__).resolve().parents[1]

def create_profile(certificate, output):
    ca=x509.load_pem_x509_certificate(Path(certificate).read_bytes())
    if not ca.extensions.get_extension_for_class(x509.BasicConstraints).value.ca:
        raise ValueError('Expected the local CA public certificate')
    fingerprint=ca.fingerprint(hashes.SHA256()).hex()
    def identifier(kind):return str(uuid.uuid5(uuid.NAMESPACE_URL,'clinical-tutor:'+fingerprint+':'+kind)).upper()
    profile={'PayloadType':'Configuration','PayloadVersion':1,
        'PayloadIdentifier':'local.clinical-tutor.ca-profile.'+fingerprint[:16],
        'PayloadUUID':identifier('profile'),'PayloadDisplayName':'Clinical Tutor Local Network CA',
        'PayloadDescription':'Installs the public certificate for your local teaching host. After installation, enable trust in Settings > General > About > Certificate Trust Settings. Remove this profile when no longer using this host.',
        'PayloadRemovalDisallowed':False,
        'PayloadContent':[{'PayloadType':'com.apple.security.root','PayloadVersion':1,
            'PayloadIdentifier':'local.clinical-tutor.root.'+fingerprint[:16],
            'PayloadUUID':identifier('certificate'),'PayloadDisplayName':'Clinical Tutor Local Network CA',
            'PayloadCertificateFileName':'clinical-tutor-ca.cer',
            'PayloadContent':ca.public_bytes(serialization.Encoding.DER)}]}
    Path(output).write_bytes(plistlib.dumps(profile,fmt=plistlib.FMT_XML))
    return fingerprint

if __name__=='__main__':
    print(create_profile(ROOT/'runtime/lan-tls/clinical-tutor-ca.cer',ROOT/'web_portal/clinical-tutor-iphone.mobileconfig'))
