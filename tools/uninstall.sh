#!/bin/sh
###########################################
####  transformers project uninstall shell file  ###
####  2016/1/14                         ###
###########################################

#transformers api service IP
API_SERVICE_IP=162.3.140.21
API_SERVICE_PORT=9900

#keystone connect info
AUTH_URL_IP=identity.az01.shenzhen--fusionsphere.huawei.com
AUTH_URL_PORT=443

#image2docker file
IMG_SERVICE_NAME=image2docker
ROOTWRAP_SERVICE_NAME=transformers-rootwrap

#transformers api service name
API_SERVICE_NAME=transformers-api

#transformers convert service name
CONVERT_SERVICE_NAME=transformers-convert

#transformers api service register user name
API_REGISTER_USER_NAME=transformers

#transformers api service register user password
API_REGISTER_USER_PASSWD=FusionSphere123

#transformers api register relation role name
API_REGISTER_ROLE_NAME=admin

#transformers api register relation tenant name
API_REGISTER_TENANT_NAME=service

#transformers api service register service name
API_REGISTER_SERVICE_NAME=transformers

#transformers api service register service type
API_REGISTER_SERVICE_TYPE=transformers

#fsp username
FSP_NAME=cloud_admin

#fsp region name
FSP_REGION_NAME=az01.shenzhen--fusionsphere


#source code file directory
CODE_DIR=/usr/local/lib/python2.7/dist-packages/transformers
CONFIG_DIR=/etc/transformers
BIN_DIR=/usr/bin
LOG_DIR=/var/log/transformers
LOG_FILE=${LOG_DIR}/transformers_uninstall.log
TIME_CMD=`date '+%Y-%m-%d %H:%M:%S'`

#get token
echo "get token from keystone"
t=$(curl --insecure https://${AUTH_URL_IP}:${AUTH_URL_PORT}/identity-admin/v2.0/tokens?format=json -X POST \
-H "Accept: application/json" -H "Content-Type: application/json" -H "User-Agent: python-novaclient" \
-d '{"auth": {"tenantName": "'${API_REGISTER_ROLE_NAME}'", "passwordCredentials": {"username": "'${FSP_NAME}'", "password": "'${API_REGISTER_USER_PASSWD}'"}}}' 2>/dev/null | python -c 'import os;r="";p=1
while p:p=os.read(0, 2**16);r+=p
import json;a=json.loads(r);print(a["access"]["token"]["id"]);')

#####################################################################
# Function: generate_log_file
# Description: generate log file
# Parameter:
# input:
# $1 -- NA 
# $2 -- NA
# output: NA
# Return:
# RET_OK
# Since: 
#
# Others:NA
#######################################################################
generate_log_file()
{ 
    if [ ! -d ${LOG_DIR} ]; then
	   mkdir -p ${LOG_DIR}
	fi
	
	if [ ! -f ${LOG_FILE} ]; then
	   touch ${LOG_FILE}
	fi
}

####################################################################
# Function: clear_files
# Description: clear transformers project files.
# Parameter:
# input:
# $1 -- NA 
# $2 -- NA
# output: NA
# Return:
# RET_OK
# Since: 
#
# Others:NA
#####################################################################
clear_files()
{
    #remove bin file 
    rm -f ${BIN_DIR}/${API_SERVICE_NAME}	

    rm -f ${BIN_DIR}/${CONVERT_SERVICE_NAME}	

	#remove image2docker file
	rm -f ${BIN_DIR}/$IMG_SERVICE_NAME
	
	#remove ROOTWRAP_SERVICE_NAME file
	rm -f ${BIN_DIR}/$ROOTWRAP_SERVICE_NAME
   
	#remove source code files
	rm -rf ${CODE_DIR}
	
	#remove config files
	rm -rf ${CONFIG_DIR}
}

####################################################################
# Function: clean_register_info
# Description: clean transformers project register information in keystone.
# Parameter:
# input:
# $1 -- NA 
# $2 -- NA
# output: NA
# Return:
# RET_OK
# Since: 
#
# Others:NA
#####################################################################
clean_register_info()
{
    echo "delete user_id"
    r=$(curl  --insecure https://${AUTH_URL_IP}:${AUTH_URL_PORT}/identity-admin/v2.0/users?format=json -X GET -H "X-Auth-Token: $t"  2>/dev/null | python  -c 'import os;import json;r = os.read(0,2**16); a = json.loads(r); u=[i["id"] for i in a["users"] if i["username"] == "transformers"];print(u[0] if len(u) else "NULL")')
    echo $r
    if [ "'$r'" != "NULL" ]; then
        $(curl -i --insecure -X DELETE https://${AUTH_URL_IP}:${AUTH_URL_PORT}/identity-admin/v2.0/users/${r} \
-H "User-Agent: python-keystoneclient" -H "X-Auth-Token: $t" 2>/dev/null)
    fi

    s_id=$(curl --insecure -X GET https://${AUTH_URL_IP}:${AUTH_URL_PORT}/identity-admin/v2.0/OS-KSADM/services -H "User-Agent: python-keystoneclient" -H "X-Auth-Token: ${t}" 2>/dev/null | python -c 'import os;import json;r = os.read(0,2**16); a = json.loads(r); u=[i["id"] for i in a["OS-KSADM:services"] if i["name"] == "transformers"];print(u[0] if len(u) else "NULL")')
    echo $s_id
    if [ "'$s_id'" != "NULL" ]; then
        ep=$(curl --insecure -X GET https://${AUTH_URL_IP}:${AUTH_URL_PORT}/identity-admin/v2.0/endpoints \
-H "User-Agent: python-keystoneclient" -H "X-Auth-Token: $t" 2>/dev/null | python -c 'import os;import json;r="";p=1;
while p:p=os.read(0,2**16);r+=p
a=json.loads(r);u=[i["id"] for i in a["endpoints"] if i["publicurl"].find("9900") != -1];print(u[0] if len(u) else "NULL")')
        echo $ep
        echo "delete endpoint"
        $(curl --insecure -X DELETE https://${AUTH_URL_IP}:${AUTH_URL_PORT}/identity-admin/v2.0/endpoints/$ep \
-H "User-Agent: python-keystoneclient" -H "X-Auth-Token: $t" 2>/dev/null)
		echo "delete service_id"
        $(curl --insecure -X DELETE https://${AUTH_URL_IP}:${AUTH_URL_PORT}/identity-admin/v2.0/OS-KSADM/services/${s_id} \
-H "User-Agent: python-keystoneclient" -H "X-Auth-Token: ${t}" 2>/dev/null)
    fi
}

stop()
{
    ps aux|grep ${API_SERVICE_NAME}|awk '{print $2}'|xargs kill -9
	
	if [ $? -eq 0 ]; then
	   echo  ${TIME_CMD} "stop api service success" >> "${LOG_FILE}"
	else
	  #log error
	  echo  ${TIME_CMD} "stop api service error" >> "${LOG_FILE}"
	fi
	
	ps aux|grep ${CONVERT_SERVICE_NAME}|awk '{print $2}'|xargs kill -9
	
	if [ $? -eq 0 ]; then
	   echo  ${TIME_CMD} "stop convert service success" >> "${LOG_FILE}"
	else
	  #log error
	  echo  ${TIME_CMD} "stop convert service error" >> "${LOG_FILE}"
	fi
}

####################################################################
# Function: main
# Description: main func.
# Parameter:
# input:
# $1 -- NA 
# $2 -- NA
# output: NA
# Return:
# RET_OK
# Since: 
#
# Others:NA
#####################################################################
main()
{
   generate_log_file
   #stop service 
   stop
 
   #clear all files
   clear_files
   
   #clean register info in keystone
   clean_register_info
}

main $@


