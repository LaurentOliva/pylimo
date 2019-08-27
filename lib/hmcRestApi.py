#!/usr/bin/python
# -*- coding: iso-8859-15 -*-
#

import sys, time, logging, socket, httplib, argparse, re, ConfigParser
from io import StringIO, BytesIO
from lxml.builder import ElementMaker
from lxml import objectify, etree

xmlns = 'http://www.ibm.com/xmlns/systems/power/firmware/web/mc/2012_10/'
xmlns2 = 'http://www.ibm.com/xmlns/systems/power/firmware/uom/mc/2012_10/'

class hmcRestApi:
    def __init__(self, hmc, hmc_port, log):
        self.hmc = hmc
        self.hmc_port = hmc_port
        self.log = log
        try:
            self.cnx = httplib.HTTPSConnection(self.hmc + ":" + self.hmc_port)
            self.cnx.connect()
        except Exception as e:
            self.log.error('Impossible d\'établir une connexion vers la HMC : ')
            self.log.debug(str(e))
            sys.exit(1)

    def getToken(self, user, password):
        self.user = user
        self.password = password

        #----------------------
        # génération flux xml
        #----------------------
        E = objectify.ElementMaker(annotate=False, namespace=xmlns, nsmap={None : xmlns})
        root = E.LogonRequest(E.Metadata(E.Atom), E.UserID(self.user, kb="CUR", kxe="false"), E.Password(self.password, kb="CUR", kxe="false"), schemaVersion="V1_1_0")
        body = etree.tostring(root, pretty_print=True, xml_declaration=True, encoding=u"UTF-8", standalone=u"yes")

        #---------------------
        # envoi requête PUT
        #---------------------
        headers = {"Content-type":"application/vnd.ibm.powervm.web+xml", "Accept":"application/vnd.ibm.powervm.web+xml"}
        self.log.debug('Requête HTTP : PUT /rest/api/web/Logon')
        self.log.debug('Requête HTTP body : \n' + body)
        self.cnx.request("PUT", "/rest/api/web/Logon", body, headers)

        #--------------------------
        # traitement réponse HTTP
        #--------------------------
        reponse = self.cnx.getresponse()
        self.log.debug('HTTP Status Code : ' + str(reponse.status) + ' ' + str(reponse.reason))
        self.log.debug('HTTP headers : \n' + str(reponse.msg))
        result = reponse.read()
        root = etree.fromstring(result)
        #log.debug(result)
        if ( reponse.status == 200 ):
            res = root.xpath('//n:X-API-Session/text()', namespaces={'n': xmlns})
            if res is not None: self.token = res[0] ; return res[0]
            if res is None: self.token = None ; return None
        if ( reponse.status != 200 ):
            res1 = root.xpath('//n:RequestURI/text()', namespaces={'n': xmlns})
            res2 = root.xpath('//n:ReasonCode/text()', namespaces={'n': xmlns})
            res3 = root.xpath('//n:Message/text()', namespaces={'n': xmlns})
            self.log.debug('RequestURI : ' + str(res1[0]))
            self.log.debug('ReasonCode : ' + str(res2[0]))
            self.log.debug('Message : ' + str(res3[0]))
            return None

    def loadLparInfos(self, lpar):
        self.lpar = lpar
        headers = {"Accept":"application/atom+xml", "X-API-Session":self.token}
        self.log.debug('Requête HTTP : GET /rest/api/uom/LogicalPartition/search/(PartitionName==' + self.lpar + ')')
        body = ''
        self.cnx.request("GET", "/rest/api/uom/LogicalPartition/search/(PartitionName==" + self.lpar + ")", body, headers)
        reponse = self.cnx.getresponse()
        self.log.debug('HTTP Status Code : ' + str(reponse.status) + ' ' + str(reponse.reason))
        self.log.debug('HTTP headers : \n' + str(reponse.msg))
        result = reponse.read()
        if ( reponse.status == 200 ):
            self.xmlLparInfos = etree.fromstring(result)
            return etree.fromstring(result)
        if ( reponse.status == 204 ):
            self.xmlLparInfos = None
            return None
        if ( reponse.status != 200 and reponse.status != 204):
            root = etree.fromstring(result)
            res1 = root.xpath('//n:RequestURI/text()', namespaces={'n': xmlns})
            res2 = root.xpath('//n:ReasonCode/text()', namespaces={'n': xmlns})
            res3 = root.xpath('//n:Message/text()', namespaces={'n': xmlns})
            self.log.debug('RequestURI : ' + str(res1[0]))
            self.log.debug('ReasonCode : ' + str(res2[0]))
            self.log.debug('Message : ' + str(res3[0]))
            return None

    def getLparUuid(self):
        return self.xmlLparInfos.xpath('//n:AtomID/text()', namespaces={'n': xmlns2})[0]
    def getHmcUuid(self):
        return self.xmlLparInfos.xpath('//n:link[@rel="MANAGEMENT_CONSOLE"]/@href', namespaces={'n': "http://www.w3.org/2005/Atom"})[0].split("/")[7]
    def getManagedSystemUuid(self):
        return self.xmlLparInfos.xpath('//n:AssociatedManagedSystem/@href', namespaces={'n': xmlns2})[0].split("/")[7]
    def getResourceMonitoringControlState(self):
        return self.xmlLparInfos.xpath('//n:ResourceMonitoringControlState/text()', namespaces={'n': xmlns2})[0]
    def getVirtualSCSIClientAdapters(self):
        return [i.split("/")[9] for i in self.xmlLparInfos.xpath('//n:VirtualSCSIClientAdapters/n:link/@href', namespaces={'n': xmlns2})]
    def getVirtualFibreChannelClientAdapters(self):
        return [i.split("/")[9] for i in self.xmlLparInfos.xpath('//n:VirtualFibreChannelClientAdapters/n:link/@href', namespaces={'n': xmlns2})]
    def getManagedSystemName(self, managedSystemUuid):
        self.managedSystemUuid = managedSystemUuid
        headers = {"Accept":"application/json", "X-API-Session":self.token}
        body=''
        self.log.debug('Requête HTTP : GET /rest/api/uom/ManagedSystem/' + self.managedSystemUuid + '/quick/SystemName')
        self.cnx.request("GET", "/rest/api/uom/ManagedSystem/" + self.managedSystemUuid + "/quick/SystemName", body, headers)
        reponse = self.cnx.getresponse()
        self.log.debug('HTTP Status Code : ' + str(reponse.status) + ' ' + str(reponse.reason))
        self.log.debug('HTTP headers : \n' + str(reponse.msg))
        self.managedSystemName = reponse.read()
        return self.managedSystemName
    def getVirtualSCSIClientAdapterInfos(self, vscsiUUID, lparUUID):
        self.vscsiUUID = vscsiUUID
        self.lparUUID = lparUUID
        headers = {"Accept":"application/atom+xml", "X-API-Session":self.token}
        body=''
        self.log.debug('Requête HTTP : GET /rest/api/uom/LogicalPartition/' + self.lparUUID + '/VirtualSCSIClientAdapter/' + self.vscsiUUID)
        self.cnx.request("GET", "/rest/api/uom/LogicalPartition/" + self.lparUUID + "/VirtualSCSIClientAdapter/" + self.vscsiUUID, body, headers)
        reponse = self.cnx.getresponse()
        self.log.debug('HTTP Status Code : ' + str(reponse.status) + ' ' + str(reponse.reason))
        self.log.debug('HTTP headers : \n' + str(reponse.msg))
        result = reponse.read()
        if ( reponse.status == 200 ):
            self.xmlVscsiInfos = etree.fromstring(result)
            return self.xmlVscsiInfos
        else:
            return None

    def getViosIdFromVscsiClientAdapter(self):
        self.vioId = self.xmlVscsiInfos.xpath('//n:AdapterType[text()="Client"]/following-sibling::n:RemoteLogicalPartitionID[1]/text()', namespaces={'n': xmlns2})[0]
        return self.vioId

    def doCLIRunner(self, hmcUUID, command):
        self.hmcUUID = hmcUUID
        self.command = command

        NSMAP = {
                'JobRequest' : 'http://www.ibm.com/xmlns/systems/power/firmware/web/mc/2012_10/',
                None : 'http://www.ibm.com/xmlns/systems/power/firmware/web/mc/2012_10/',
                'ns2' : 'http://www.w3.org/XML/1998/namespace/k2'
                }

        E = objectify.ElementMaker(annotate=False, namespace=NSMAP['JobRequest'], nsmap=NSMAP)
        F = objectify.ElementMaker(annotate=False, namespace=None, nsmap=None)
        root = E.JobRequest(F.Metadata(F.Atom), F.RequestedOperation(F.Metadata(F.Atom), F.OperationName("CLIRunner", kxe="false", kb="ROR"),  F.GroupName("ManagementConsole", kxe="false", kb="ROR"), kxe="false", kb="CUR", schemaVersion="V1_2_0"), F.JobParameters(F.Metadata(F.Atom), F.JobParameter(F.Metadata(F.Atom), F.ParameterName("cmd", kxe="false", kb="ROR"), F.ParameterValue(self.command, kxe="false", kb="CUR"), schemaVersion="V1_0"), F.JobParameter(F.Metadata(F.Atom), F.ParameterName("acknowledgeThisAPIMayGoAwayInTheFuture", kxe="false", kb="ROR"), F.ParameterValue("true", kxe="false", kb="CUR"), schemaVersion="V1_0"), kxe="false", kb="CUR", schemaVersion="V1_2_0"), schemaVersion="V1_2_0")

        headers = {"Content-Type":"application/vnd.ibm.powervm.web+xml; type=JobRequest", "X-API-Session":self.token}
        body = etree.tostring(root, pretty_print=True, xml_declaration=False)
        self.log.debug('Requête HTTP : PUT /rest/api/uom/ManagementConsole/' + self.hmcUUID + '/do/CLIRunner')
        self.cnx.request("PUT", "/rest/api/uom/ManagementConsole/" + self.hmcUUID + "/do/CLIRunner", body, headers)
        reponse = self.cnx.getresponse()
        self.log.debug('HTTP Status Code : ' + str(reponse.status) + ' ' + str(reponse.reason))
        self.log.debug('HTTP headers : \n' + str(reponse.msg))
        result = reponse.read()
        if ( reponse.status == 200 ):
            xmlLocal = etree.fromstring(result)
            self.jobID = xmlLocal.xpath('//n:JobID/text()', namespaces={'n': xmlns})
            return self.jobID[0]
        else:
            self.log.debug('ERREUR : \n' + result)
            return None
    def getJobStatus(self, jobID):
        self.jobID = jobID
        headers = {"Accept":"application/atom+xml", "Expect":"" , "Content-Type":"application/vnd.ibm.powervm.web+xml; type=JobRequest", "X-API-Session":self.token}
        body = ''
        self.log.debug('Requête HTTP : GET /rest/api/uom/jobs/' + self.jobID)
        self.cnx.request("GET", "/rest/api/uom/jobs/" + self.jobID, body, headers)
        response = self.cnx.getresponse().read()
        root = etree.fromstring(response)
        res = root.xpath('//n:Status/text()', namespaces={'n': xmlns})
        if res[0] != "RUNNING" and res[0] != "NOT_STARTED":
            self.log.debug(root.xpath('//n:ParameterName[1]/text()', namespaces={'n': xmlns})[0] + " ==> " + root.xpath('//n:ParameterValue[1]/text()', namespaces={'n': xmlns})[0])
            self.log.debug(root.xpath('//n:Results/n:JobParameter[1]/n:ParameterName/text()', namespaces={'n': xmlns})[0] + " ==> " + root.xpath('//n:Results/n:JobParameter[1]/n:ParameterValue/text()', namespaces={'n': xmlns})[0])
            self.log.debug(root.xpath('//n:Results/n:JobParameter[2]/n:ParameterName/text()', namespaces={'n': xmlns})[0] + " ==> " + root.xpath('//n:Results/n:JobParameter[2]/n:ParameterValue/text()', namespaces={'n': xmlns})[0])
            self.log.debug("")
        return res[0]

