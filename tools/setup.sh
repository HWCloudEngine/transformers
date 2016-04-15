#!/bin/sh
####################################################
####  transformers project install shell file    ###
####  2016/3/15                                  ###
####################################################

#transformers api service IP
API_SERVICE_IP=162.3.140.21
API_SERVICE_PORT=9900

#keystone connect info
AUTH_URL_IP=identity.az01.shenzhen--fusionsphere.huawei.com
AUTH_URL_PORT=443

#fsp username
FSP_NAME=cloud_admin

#fsp region name
FSP_REGION_NAME=az01.shenzhen--fusionsphere

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

#source code file directory
CODE_DIR=/usr/local/lib/python2.7/dist-packages/
CONFIG_DIR=/etc/transformers
BIN_DIR=/usr/bin
API_CONFIG_FILE=hybrid-transformers.conf
PROJECT_NAME=transformers

#CONSISTENT VARIABLE VALUE
LOG_DIR=/var/log/transformers
LOG_FILE=${LOG_DIR}/install.log
API_LOG=${LOG_DIR}/api.log
CONVERT_LOG=${LOG_DIR}/convert.log
TIME_CMD=`date '+%Y-%m-%d %H:%M:%S'`
BOOL_TRUE_INT=0
BOOL_FALSE_INT=1
ERROR_INT=2

generate_log_file()
{ 
    if [ ! -d ${LOG_DIR} ]; then
	   mkdir -p ${LOG_DIR}
	fi
	
	if [ ! -f ${LOG_FILE} ]; then
	   touch ${LOG_FILE}
	fi
}

echo "generate log file"
generate_log_file

copy_files_to_dir()
{
    #copy  running file to /usr/bin

    for f in ${ROOTWRAP_SERVICE_NAME} ${API_SERVICE_NAME} ${GATEWAY_SERVICE_NAME}; do
	
	    if [ -f ${BIN_DIR}/$f ]; then
		    rm -f ${BIN_DIR}/$f
		fi
		
        cp $f ${BIN_DIR}
		
		if [ ! -x ${BIN_DIR}/$f ]; then
		  chmod +x ${BIN_DIR}/$f
		fi
		 
    done 

	#copy image2docker file to /usr/local/bin
	if [ -f ${BIN_DIR}/$IMG_SERVICE_NAME ]; then
		rm -f ${BIN_DIR}/$IMG_SERVICE_NAME
	fi
	cp $IMG_SERVICE_NAME ${BIN_DIR}
	
    #copy source code to /usr/local/lib/python2.7/dist-packages
	if [ -d ${CODE_DIR}/${PROJECT_NAME} ]; then
	   rm -rf ${CODE_DIR}/${PROJECT_NAME}
	fi
    cp -r ../${PROJECT_NAME} ${CODE_DIR}

    #make config file directory
	if [ -d ${CONFIG_DIR} ]; then
	   rm -rf ${CONFIG_DIR}
	fi
	
    mkdir ${CONFIG_DIR}

    #copy config file to /etc/transformers
    cp ../etc/${PROJECT_NAME}/* ${CONFIG_DIR}
}

#get token
echo "get token from keystone"
t=$(curl --insecure https://${AUTH_URL_IP}:${AUTH_URL_PORT}/identity-admin/v2.0/tokens?format=json -X POST \
-H "Accept: application/json" -H "Content-Type: application/json" -H "User-Agent: python-novaclient" \
-d '{"auth": {"tenantName": "'${API_REGISTER_ROLE_NAME}'", "passwordCredentials": {"username": "'${FSP_NAME}'", "password": "'${API_REGISTER_USER_PASSWD}'"}}}' 2>/dev/null | python -c 'import os;r="";p=1
while p:p=os.read(0, 2**16);r+=p
import json;a=json.loads(r);print(a["access"]["token"]["id"]);')

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

register_services()
{
	echo "clean register info"
	clean_register_info
	
    echo "create user"
    user_id=$(curl  --insecure https://${AUTH_URL_IP}:${AUTH_URL_PORT}/identity-admin/v2.0/users -X POST -H "X-Auth-Token: $t" \
-H "Accept: application/json" -H "Content-Type: application/json" -H "User-Agent: python-novaclient" \
-d '{"user": {"name": "'${API_REGISTER_USER_NAME}'", "email": "admin@example.com", "enabled": true, "OS-KSADM:password": "'${API_REGISTER_USER_PASSWD}'"}}' 2>/dev/null \
| python -c 'import os;import json;r=os.read(0,2**16);a=json.loads(r);print(a["user"]["id"]);')
    echo "user_id: " $user_id 
    tenants_id=$(curl --insecure -X GET https://${AUTH_URL_IP}:${AUTH_URL_PORT}/identity-admin/v2.0/tenants \
-H "User-Agent: python-keystoneclient" -H "X-Auth-Token: $t" 2>/dev/null \
| python -c 'import os;import json;r=os.read(0,2**16);a=json.loads(r);print([i["id"] for i in a["tenants"] if i["name"]=="service"][0]);')
    echo "tenant_id: " $tenants_id
    role_id=$(curl --insecure -X GET https://${AUTH_URL_IP}:${AUTH_URL_PORT}/identity-admin/v2.0/OS-KSADM/roles \
-H "User-Agent: python-keystoneclient" -H "X-Auth-Token: $t" 2>/dev/null | \
python -c 'import os;import json;r=os.read(0,2**16);a=json.loads(r);print([i["id"] for i in a["roles"] if i["name"]=="admin"][0]);')
    echo "role_id: " $role_id
    echo "role add"
    $(curl --insecure https://${AUTH_URL_IP}:${AUTH_URL_PORT}/identity-admin/v2.0/tenants/${tenants_id}/users/${user_id}/roles/OS-KSADM/${role_id} -X PUT -H "User-Agent: python-keystoneclient" -H "X-Auth-Token: $t")
    echo "create service"
    service_id=$(curl --insecure -X POST https://${AUTH_URL_IP}:${AUTH_URL_PORT}/identity-admin/v2.0/OS-KSADM/services \
-H "User-Agent: python-keystoneclient" -H "Content-Type: application/json" -H "X-Auth-Token: $t" \
-d '{"OS-KSADM:service": {"type": "'${API_REGISTER_SERVICE_TYPE}'", "name": "'${API_REGISTER_SERVICE_NAME}'", "description": "hybrid image convert"}}' 2>/dev/null | \
python -c 'import os;import json;r=os.read(0,2**16);a=json.loads(r);print(a["OS-KSADM:service"]["id"]);')
    echo "service_id: " $service_id
    echo "create endpoint"
    echo "region_name: " $FSP_REGION_NAME
    `curl --insecure -X POST https://${AUTH_URL_IP}:${AUTH_URL_PORT}/identity-admin/v2.0/endpoints -H "User-Agent: python-keystoneclient" -H "Content-Type: application/json" -H "X-Auth-Token: $t" -d '{"endpoint": {"adminurl": "http://'${API_SERVICE_IP}':'${API_SERVICE_PORT}'/v1/$(tenant_id)s", "service_id": "'${service_id}'", "region": "'${FSP_REGION_NAME}'", "internalurl": "http://'${API_SERVICE_IP}':'${API_SERVICE_PORT}'/v1/$(tenant_id)s", "publicurl": "http://'${API_SERVICE_IP}':'${API_SERVICE_PORT}'/v1/$(tenant_id)s"}}' 2>/dev/null`
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

start()
{
   echo "start api service"
   ${BIN_DIR}/${API_SERVICE_NAME} --config-file ${CONFIG_DIR}/${API_CONFIG_FILE} & >> "${API_LOG}" 2>&1
   
   if [ $? -ne 0 ]; then
      echo  ${TIME_CMD} "start api service error." >> "${LOG_FILE}"
	  ${BIN_DIR}/${API_SERVICE_NAME} --config-file ${CONFIG_DIR}/${API_CONFIG_FILE} & >> "${LOG_FILE}" 2>&1
   fi
   
   echo "start convert service"
   ${BIN_DIR}/${CONVERT_SERVICE_NAME} --config-file ${CONFIG_DIR}/${API_CONFIG_FILE} & >> "${CONVERT_LOG}" 2>&1
   
   if [ $? -ne 0 ]; then
      echo  ${TIME_CMD} "start convert service error." >> "${LOG_FILE}"
	  ${BIN_DIR}/${CONVERT_SERVICE_NAME} --config-file ${CONFIG_DIR}/${API_CONFIG_FILE} & >> "${LOG_FILE}" 2>&1
   fi
}

restart() {
	stop; sleep 1; start;
}

init() {

   #register in keystone
   echo  ${TIME_CMD} "begin register transformers service."
   register_services
   echo  ${TIME_CMD} "end register transformers service." 
}

install()
{
	copy_files_to_dir

	start
}

echo init install start stop restart | grep -w ${1:-NOT} >/dev/null && $@  >> "${LOG_FILE}" 2>&1