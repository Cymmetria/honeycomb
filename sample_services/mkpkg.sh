#!/bin/bash

PL=$1
if [ -d "$PL" ]
then
	rm -rvf ${PL}_service
	rm -v ${PL}.zip
	mkdir ${PL}_service
	cp -r ${PL}/pysnmp ${PL}_service/
	cp -r ${PL}/pyasn1 ${PL}_service/
	cp ${PL}/*.py ${PL}/*.json ${PL}_service/
	cd ${PL}_service/
	find . -name \*.pyc -exec rm -v {} \;
	zip -vr ../${PL}.zip *
	cd ..
	rm -rf ${PL}_service
else
	echo "DIR: '${PL}' does not exist"
fi
