"""One shared application/store, loopback HTTP plus local-network TLS listener.

The private CA key and host key remain in ignored runtime/lan-tls. Users install
the CA certificate on their own devices; this tool never changes trust stores.
"""
import argparse,asyncio,datetime,ipaddress,json,socket,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def certificates(addresses,directory):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes,serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    directory.mkdir(parents=True,exist_ok=True);now=datetime.datetime.now(datetime.timezone.utc)
    keyfile=directory/'ca-key.pem';cafile=directory/'clinical-tutor-ca.cer'
    if keyfile.exists() and cafile.exists():
        ca_key=serialization.load_pem_private_key(keyfile.read_bytes(),None);ca=x509.load_pem_x509_certificate(cafile.read_bytes())
    else:
        ca_key=rsa.generate_private_key(public_exponent=65537,key_size=3072)
        name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Clinical Tutor Local Network CA')])
        ca=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(ca_key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(days=1)).not_valid_after(now+datetime.timedelta(days=3650)).add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True).add_extension(x509.KeyUsage(digital_signature=True,key_encipherment=False,content_commitment=False,data_encipherment=False,key_agreement=False,key_cert_sign=True,crl_sign=True,encipher_only=False,decipher_only=False),critical=True).sign(ca_key,hashes.SHA256())
        keyfile.write_bytes(ca_key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));cafile.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    # OpenSSL 3.4 strict verification (Python 3.13+) requires issuer key IDs.
    try:ca.extensions.get_extension_for_class(x509.SubjectKeyIdentifier)
    except x509.ExtensionNotFound:
        ca=x509.CertificateBuilder().subject_name(ca.subject).issuer_name(ca.subject).public_key(ca_key.public_key()).serial_number(ca.serial_number).not_valid_before(ca.not_valid_before_utc).not_valid_after(ca.not_valid_after_utc).add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True).add_extension(x509.KeyUsage(digital_signature=True,key_encipherment=False,content_commitment=False,data_encipherment=False,key_agreement=False,key_cert_sign=True,crl_sign=True,encipher_only=False,decipher_only=False),critical=True).add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),critical=False).add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),critical=False).sign(ca_key,hashes.SHA256())
        cafile.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    san=[x509.DNSName('localhost'),x509.DNSName(socket.gethostname())]+[x509.IPAddress(ipaddress.ip_address(ip)) for ip in sorted(set(addresses+['127.0.0.1']))]
    cert=x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Clinical Tutor LAN')])).issuer_name(ca.subject).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(days=1)).not_valid_after(now+datetime.timedelta(days=365)).add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True).add_extension(x509.SubjectAlternativeName(san),critical=False).add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()),critical=False).add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),critical=False).add_extension(x509.KeyUsage(digital_signature=True,key_encipherment=True,content_commitment=False,data_encipherment=False,key_agreement=False,key_cert_sign=False,crl_sign=False,encipher_only=False,decipher_only=False),critical=True).add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),critical=False).sign(ca_key,hashes.SHA256())
    (directory/'server-key.pem').write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));(directory/'server.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return directory/'server.pem',directory/'server-key.pem'

async def serve(addresses,https_port):
    import uvicorn
    from backend.server import app
    cert,key=certificates(addresses,ROOT/'runtime/lan-tls')
    urls=[f'https://{ip}:{https_port}/login' for ip in addresses]
    (ROOT/'runtime/lan-tls/connection.json').write_text(json.dumps({'urls':urls,'ca_certificate':'clinical-tutor-ca.cer','requires_client_certificate_trust':True},indent=2),encoding='utf-8')
    print(json.dumps({'local':'http://127.0.0.1:8705/login','lan':urls,'certificate':str(cert.parent/'clinical-tutor-ca.cer')},ensure_ascii=False),flush=True)
    local=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8705,log_level='info'))
    secure=uvicorn.Server(uvicorn.Config(app,host='0.0.0.0',port=https_port,ssl_certfile=str(cert),ssl_keyfile=str(key),lifespan='off',log_level='info'))
    await asyncio.gather(local.serve(),secure.serve())

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--address',action='append',required=True);p.add_argument('--https-port',type=int,default=8765);a=p.parse_args()
    asyncio.run(serve(a.address,a.https_port))
