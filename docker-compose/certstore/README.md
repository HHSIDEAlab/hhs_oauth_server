# Put BB2 server's cert & key for secured connection with BFD FHIR server

ca.cert.pem - certificate
ca.key.nocrypt.pem - private key

Ask for cert and key that works with the
targeted BFD FHIR server.

For a local BFD FHIR server using dev and test client cert and key,
follow below steps to obtain above cert and key file:

(1) git clone https://github.com/CMSgov/beneficiary-fhir-data.git
(2) the pfx file containing client cert and key for bfd local is at beneficiary-fhir-data\apps\bfd-server\dev\ssl-stores\client-trusted-keystore.pfx
(3) extract cert and key (in .pem format) from pfx, e.g. using openssl as shown below:
(3.1) openssl pkcs12 -in client-trusted-keystore.pfx -nocerts -out ca.key.nocrypt.pem -nodes
(3.2) openssl pkcs12 -in client-trusted-keystore.pfx -nokeys -out ca.cert.pem  
