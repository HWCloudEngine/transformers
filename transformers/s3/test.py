from s3 import API

driver = API('AKIAJVWHRZAEI4IXXKEA', 'WeDng5cErKQKrQwaGiK2UuMP3nn9KonJjlpdIOWi', secure=False, region='ap-southeast-1')
print driver.get_container('wfse1')

obj = driver.get_object('wfse1', 'swft')
print obj


print '----end----'