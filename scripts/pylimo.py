#!/usr/bin/python
# -*- coding: iso-8859-15 -*-
#
# pYLiMo : pYthon Live partition Mobility validation tool
#
# Date : April - July 2015
#
# Author : Laurent Oliva
#
import MySQLdb
import os, sys, time, logging, socket, httplib, argparse, re, ConfigParser
## lib location
sys.path.append('/produits/aixadm/pylimo/lib')
#from io import StringIO, BytesIO
#from lxml.builder import ElementMaker
from lxml import objectify, etree
from threading import Thread
from logging.handlers import RotatingFileHandler
from hmcRestApi import *

## versioning
__version__ = "$Revision: 10000 $"

#######
####### Global variables
#######

xmlns = 'http://www.ibm.com/xmlns/systems/power/firmware/web/mc/2012_10/'
xmlns2 = 'http://www.ibm.com/xmlns/systems/power/firmware/uom/mc/2012_10/'

pylimo_root = '/produits/aixadm/pylimo'
pylimo_log = pylimo_root + '/logs/'
pylimo_output = pylimo_root + '/outputs/'

xslt_sheet_path = 'format_lpmOutput.xsl'

######
###### Fonctions
######

def initLogging(verbose=False):
    """
    initLogging() : Cette fonction initialise le logger racine permettant d'afficher les messages du fil d'exécution principal du script.

    Les messages sont affichés sur la sortie standard si le script est exécuté en intéractif.
    Sinon, ils sont consignés dans un fichier circulaire.
    
    La fonction renvoie un objet de type logging.

    Cet objet sera ensuite eventuellement utilisé dans certaines fonctions ou classes, de manière à ce que les messages importants soient affichés dans le fil d'exécution principal.

    Un filtre est appliqué au logger de manière à ce que les messages ne soient pas propagés aux logger dont le nom ne commence pas par 'root'
    
    """

    logger = logging.getLogger('root')
    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')

    ## log handler dans un fichier
    logger_handler = RotatingFileHandler(pylimo_log + args.lpar + "_LPM_validate.log", 'a', 10240, 5, encoding=None)

    ## si le script est appelé en mode interactif...
    if sys.__stdin__.isatty():
        logger_handler2 = logging.StreamHandler()
        logger_handler2.addFilter(logging.Filter('root'))
        logger_handler2.setFormatter(formatter)
        logger.addHandler(logger_handler2)

    logger_handler.addFilter(logging.Filter('root'))
    logger.setLevel(logging.INFO) if verbose == False else logger.setLevel(logging.DEBUG)
    logger_handler.setFormatter(formatter)
    logger.addHandler(logger_handler)
    logger_handler.doRollover()

    return logger

###### (*) Fonctions 
######     ---------

def connectMysql(hostname, user, password, schema):
    """
    connectMysql(hostname, user, password, schema)
    Cette fonction se connecte à la base Mysql fournie en paramètre et retourne un objet
    permettant d utiliser cette connexion

    Si une erreur est rencontrée, la fonction renvoie une exception qu'il faut catcher
    """

    mydb = MySQLdb.connect(hostname, user, password, schema)
    return mydb

def getMyLocation(db, lpar):
    """
    getMyLocation(db, lpar)
    Cette fcontion prend pour paramètre une DB MySQL et une LPAR.

    Cette LPAR est recherchée dans la base de donnée 'serversystemaix' hébergée sur PAIX01 en principe.
    """

    cursor = db.cursor()
    query = """SELECT PLTNAME,SITE,HMCNAME1,HMCNAME2,lpm_capable FROM platform_reference WHERE SERIAL = ( SELECT SUBSTRING(SN, -7) FROM host_platform WHERE HOSTNAME = %s ) LIMIT 1 """

    lines = cursor.execute(query, (lpar,))
    if int(cursor.rowcount) < 1: return None

    while True:
        row = cursor.fetchone()
        if row != None: my_result = {"frame":row[0], "site":row[1], "hmc1":row[2], "hmc2":row[3], "lpm":row[4]}
        if row == None: break
    return my_result

def getAllLPMFrame(db, my_site, my_frame):
    """
    getAllLPMFrame(db, my_site, my_frame)
    Cette fonction prend pour paramètre une DB MySQL, un site/datacenter et un châssis.

    Elle retourne la liste des frame 'LPM Ready' du site passé en paramètre.
    """

    my_result = []
    cursor = db.cursor()
    query = """ SELECT PLTNAME,HMCNAME1,HMCNAME2 FROM platform_reference WHERE SITE = %s AND lpm_capable = 1 AND STATE = 'Operating' AND PLTNAME <> %s"""

    lines = cursor.execute(query, (my_site, my_frame))
    if int(cursor.rowcount) < 1: return None

    while True:
        row = cursor.fetchone()
        if row != None: my_result.append(row[0] + ";" + row[1] + ";" + row[2])
        if row == None: break
    return my_result

def genXMLJob(E, jobName, jobValue):
    """
    genXMLJob(E, jobName, jobValue) : Cette fonction prend trois paramètres

    Elle génère un ensemble de balises XML standard formant la syntaxe d'un job parameter de l'API REST.

    """
    XMLJob = E.JobParameter(E.Metadata(E.Atom), E.ParameterName(jobName, kxe="false", kb="ROR"), E.ParameterValue(jobValue, kxe="false", kb="CUR"), schemaVersion="V1_0")
    return XMLJob

def getLPMValidateJobStatus(hmc, token, lpmJobID, targetFrame, verbose=None):
    conn = httplib.HTTPSConnection(hmc + ":12443")
    headers = {"Accept":"application/atom+xml", "Expect":"", "Content-Type":"application/vnd.ibm.powervm.web+xml; type=JobRequest", "X-API-Session":token}
    body = ''

    conn.request("GET", "/rest/api/uom/jobs/" + lpmJobID, body, headers)
    response = conn.getresponse().read()
    root = etree.fromstring(response)

    res = root.xpath('//n:Status/text()', namespaces={'n': 'http://www.ibm.com/xmlns/systems/power/firmware/web/mc/2012_10/'})
    my_result = {"status":res[0]}

    res = root.xpath('//n:TimeStarted/text()', namespaces={'n': 'http://www.ibm.com/xmlns/systems/power/firmware/web/mc/2012_10/'})
    my_result["timestarted"] = res[0]

    res = root.xpath('//n:TimeCompleted/text()', namespaces={'n': 'http://www.ibm.com/xmlns/systems/power/firmware/web/mc/2012_10/'})
    my_result["timecompleted"] = res[0]

    ## commits xml output job result onto disk files
    if re.match(r"^COMPLETED", my_result["status"]):
        logger = logging.getLogger('output.' + lpmJobID)
        logger.setLevel(logging.INFO)

        outfile = logging.FileHandler(pylimo_output + args.lpar + '.' + targetFrame + '.' + hmc + '.' + lpmJobID + '.xml')
        outfile.addFilter(logging.Filter('output.' + lpmJobID))
        logger.addHandler(outfile)
        logger.info('<?xml-stylesheet href="' + xslt_sheet_path + '" type="text/xsl" ?> ')
        logger.info(response)
        outfile.close()

    return my_result

###### (*) Classes
######     -------

class doLPMValidateJob(Thread):
    def __init__(self, log, hmc, token, lpar, uuid, targetFrame, targetHMC=None):
        Thread.__init__(self)
        self.hmc = hmc
        self.token = token
        self.lpar = lpar
        self.uuid = uuid
        self.targetFrame = targetFrame
        self.targetHMC = targetHMC
        self.log = log

        #if ( targetHMC != None):

            ## Gets IP address of the targetHMC
        #    s = socket.gethostbyaddr(self.targetHMC)
        #    for i in s[-1]:
        #        self.targetHMC = i

    def run(self):

        E = objectify.ElementMaker(annotate=False, namespace=xmlns, nsmap={None : xmlns})

        if self.targetHMC != None:
            jParam_targetHMC = genXMLJob(E, 'TargetRemoteHMCIPAddress', self.targetHMC)
            jParam_targetHMCUserID = genXMLJob(E, 'TargetRemoteHMCUserID', 'hscroot')

        jParam_targetFRAME = genXMLJob(E, 'TargetManagedSystemName', self.targetFrame)

        if self.targetHMC != None:
            root = E.JobRequest(E.Metadata(E.Atom), E.RequestedOperation(E.Metadata(E.Atom), E.OperationName("MigrateValidate", kxe="false", kb="ROR"), E.GroupName('LogicalPartition', kxe="false", kb="ROR"), E.ProgressType('DISCRETE', kxe="false", kb="ROR"), kxe="false", kb="CUR", schemaVersion="V1_0"), E.JobParameters(E.Metadata(E.Atom), jParam_targetHMC, jParam_targetHMCUserID, jParam_targetFRAME, kxe="false", kb="CUR", schemaVersion="V1_0"), schemaVersion="V1_0")
        else:
            root = E.JobRequest(E.Metadata(E.Atom), E.RequestedOperation(E.Metadata(E.Atom), E.OperationName("MigrateValidate", kxe="false", kb="ROR"), E.GroupName('LogicalPartition', kxe="false", kb="ROR"), E.ProgressType('DISCRETE', kxe="false", kb="ROR"), kxe="false", kb="CUR", schemaVersion="V1_0"), E.JobParameters(E.Metadata(E.Atom), jParam_targetFRAME, kxe="false", kb="CUR", schemaVersion="V1_0"), schemaVersion="V1_0")

        conn = httplib.HTTPSConnection(self.hmc + ":12443")
        headers = {"Accept":"application/atom+xml", "Expect":"", "Content-Type":"application/vnd.ibm.powervm.web+xml; type=JobRequest", "X-API-Session":self.token}
        body = etree.tostring(root, pretty_print=True, xml_declaration=True, encoding=u"UTF-8", standalone=u"yes")

        conn.request("PUT", "/rest/api/uom/LogicalPartition/" + self.uuid + "/do/MigrateValidate", body, headers)
        response = conn.getresponse().read()
        root = etree.fromstring(response)
        res = root.xpath('//n:JobID/text()', namespaces={'n': 'http://www.ibm.com/xmlns/systems/power/firmware/web/mc/2012_10/'})

        LPMValidateResults = getLPMValidateJobStatus(hmc=self.hmc, token=self.token, lpmJobID=res[0], targetFrame=self.targetFrame, verbose=None)
        while LPMValidateResults["status"] == "RUNNING" or LPMValidateResults["status"] == "NOT_STARTED":
            LPMValidateResults = getLPMValidateJobStatus(hmc=self.hmc, token=self.token, lpmJobID=res[0], targetFrame=self.targetFrame, verbose=None)
            time.sleep(1)

        if self.targetHMC != None:
            self.log.info('[' + self.getName() + '] | LPM Validate JobID : ' + res[0] + ' | LPAR : ' + self.lpar + ' | HMC source : ' + self.hmc + ' | FRAME cible : ' + self.targetFrame + ' | HMC cible : ' + self.targetHMC + ' | result : ' + LPMValidateResults["status"])
        else:
            self.log.info('[' + self.getName() + '] | LPM Validate JobID : ' + res[0] + ' | LPAR : ' + self.lpar + ' | HMC source : ' + self.hmc + ' | FRAME cible : ' + self.targetFrame + ' | HMC cible : N/A | result : ' + LPMValidateResults["status"])

##############################################
##
## Main main()....
##
##############################################

#----------------------
# test les arguments
#----------------------
if len(sys.argv) < 3:
    print "usage: " + sys.argv[0] + " [-h] [-v] [-l LPAR] [-c config file]"
    sys.exit(1)

#----------------------
# parcours des args
#----------------------
parser = argparse.ArgumentParser(description='Check if LPARs given in parameter are eligible for LPM operation or not')
parser.add_argument("--lpar", "-l", help="LPAR names", action="store", type=str)
parser.add_argument("--config", "-c", help="Config ini file", action="store", type=str)
parser.add_argument("--verbose", "-v", help="Enable verbose messages", action="store_true")
args = parser.parse_args()

#--------------------
# init logger
#--------------------
log = initLogging(args.verbose)
log.info("----------------")
log.info("---- pYLiMo ----")
log.info("----------------")
log.info("")
log.info("pYthon LIve partition MObility validation tool")
log.info("")
log.info("(*) Récupération des paramètres du fichier de config")
log.info("    ------------------------------------------------")
log.info("")

#------------------------------
# test ouverture fichier conf
#------------------------------
config = ConfigParser.ConfigParser()
try:
    fh = config.readfp(open(args.config))
except Exception as e:
    log.error('Le fichier ' + args.config + ' n\'a pas pû être parcouru ou est introuvable !')
    log.debug(str(e))
    raise SystemExit(1)

#--------------------------------------------
# récupère les paramètres du fichier de conf
#--------------------------------------------
try:
    mysql_db = config.get('DB', 'com.pylimo.mysql.db')
    mysql_user = config.get('DB', 'com.pylimo.mysql.user')
    mysql_password = config.get('DB', 'com.pylimo.mysql.password')
    mysql_host = config.get('DB', 'com.pylimo.mysql.host')
    hmc_port = config.get('HMC', 'com.pylimo.hmc.port')
    hmc_user = config.get('HMC', 'com.pylimo.hmc.user')
    hmc_password = config.get('HMC', 'com.pylimo.hmc.password')
except Exception as e:
    log.error('Erreur rencontrée pendant la recupération des paramètres du fichier de config ' + args.config)
    log.debug(str(e))
    raise SystemExit(1)

#----------------------------
# connexion à la base mysql
#----------------------------
try:
    log.info("(*) Connexion à la base MySQL")
    log.info("    -------------------------")
    log.info("")
    mysql = connectMysql(mysql_host, mysql_user, mysql_password, mysql_db)
except Exception as e:
    log.error('ERREUR rencontrée lors de la connexion à la base MySQL !')
    log.debug(str(e))
    raise SystemExit(1)

#---------------------------------------
# récupération info localisation LPAR 
#---------------------------------------
try:
    log.info("(*) Récupération des informations de localisation de la LPAR : " + args.lpar)
    log.info("    --------------------------------------------------------")
    log.info("")
    result = getMyLocation(db=mysql, lpar=args.lpar)
except Exception as f:
    log.error('Erreur lors de la récupération des informations de localisation de ' + args.lpar)
    log.debug(str(f))
    raise SystemExit(1)

if result == None:
    log.error(args.lpar + ' n\'a pas été trouvé dans la base de données.')
    log.debug("Requête SQL executée : SELECT PLTNAME,SITE,HMCNAME1,HMCNAME2,lpm_capable FROM platform_reference WHERE SERIAL = ( SELECT SUBSTRING(SN, -7) FROM host_platform WHERE HOSTNAME = " + args.lpar + " ) LIMIT 1 ")
    sys.exit(1)

### (*) Si mode DEBUG activé : on affiche ce qu'on a trouvé dans la base mysql...
log.debug("LPAR : " + args.lpar + ", SITE : " + result['site'] + ", CHASSIS : " + result['frame'] + ", HMC : " + result['hmc1'])

#---------------------------------------
# on recherche les frame LPM capable 
# du même site...
#---------------------------------------
try:
    log.info("(*) Recherche des châssis du même site où le LPM est possible")
    log.info("    ---------------------------------------------------------")
    log.info("")
    result_lpm = getAllLPMFrame(db=mysql, my_site=result["site"], my_frame=result["frame"])
except Exception as g:
    log.error('Erreur lors de l\'execution de la requête SQL de la fonction getAllLPMFrame()!')
    log.debug("Requête SQL executée : SELECT PLTNAME,HMCNAME1,HMCNAME2 FROM platform_reference WHERE SITE = " + result['site'] + " AND lpm_capable = 1 AND STATE = 'Operating' AND PLTNAME <> " + result['frame'])
    log.debug(str(g))
    raise SystemExit(1)

#--------------------------
# connexion HMC...
#--------------------------
log.info("(*) Connexion à la HMC " + result["hmc1"] + " via Rest API..")
log.info("    -----------------------------------------------")
log.info("")
hmc = hmcRestApi(hmc=result["hmc1"], hmc_port=hmc_port, log=log)
token = hmc.getToken(user=hmc_user, password=hmc_password)
if token == None:
    log.error('ERREUR lors de la récupération du token X-API-SESSION ' + result["hmc1"])
    sys.exit(1)
else:
    log.info('--> token X-API-SESSION obtenu')

#---------------------------------
# récupération infos & contrôles
#---------------------------------

lparInfos = hmc.loadLparInfos(lpar=args.lpar)
if lparInfos == None:
    log.info('ERREUR lors de la récupération des informations de la LPAR ' + args.lpar)
    sys.exit(1)
else:
    log.info('--> Informations LPAR ' + args.lpar + ' collectées')
    log.info('')

lparUUID = hmc.getLparUuid()
if lparUUID == None:
    log.error('ERREUR lors de la récupération du lpar UUID de ' + args.lpar)
    sys.exit(1)

sysUUID = hmc.getManagedSystemUuid()
if sysUUID == None:
    log.error('ERREUR lors de la récupération du managed system UUID')
    sys.exit(1)

rmcState = hmc.getResourceMonitoringControlState()
if rmcState == None:
    log.error('ERREUR lors de la vérification du DLPAR (RMC)')
    sys.exit(1)

if rmcState != 'active':
    log.error('ERREUR le DLPAR n\'est pas actif sur la LPAR ' + args.lpar)
    log.debug('Valeur rmcState = ' + rmcState)
    sys.exit(1)

#------------------------------------
# traitement vscsi cdrom
#------------------------------------
vscsiClientAdapters = hmc.getVirtualSCSIClientAdapters()
viosID = []
for i in vscsiClientAdapters:
    hmc.getVirtualSCSIClientAdapterInfos(vscsiUUID=i, lparUUID=lparUUID)
    viosID.append(hmc.getViosIdFromVscsiClientAdapter())

frameName = hmc.getManagedSystemName(sysUUID)
HmcUuid = hmc.getHmcUuid()

for id in viosID:
    log.info("--> Suppression CDROM VSCSI sur VIO LPAR ID : " + id + " ...")
    log.info("    ---------------------------------------")
    log.info("")
    jobID = hmc.doCLIRunner(HmcUuid, "viosvrcmd -m " + frameName.replace('\"', '') + " --id " + id + " -c \"rmdev -dev " + args.lpar.lower() + "_cdrom\"")
    log.debug("viosvrcmd -m " + frameName.replace('\"', '') + " --id " + id + " -c \"rmdev -dev " + args.lpar.lower() + "_cdrom\"")
    jobStatus = hmc.getJobStatus(jobID)
    while jobStatus == "RUNNING" or jobStatus == "NOT_STARTED":
        time.sleep(1)
        jobStatus = hmc.getJobStatus(jobID)

#------------------------------
# LPM validate sur châssis
#------------------------------
threads = []
for element in result_lpm:
    elem = element.split(";")

    #-------------------------------------------------------------------
    # on effectue un LPM validate vers les frame gérées par la même HMC
    #-------------------------------------------------------------------
    if elem[1] == result["hmc1"]:
        thread_LPM = doLPMValidateJob(log, hmc=result["hmc1"], token=token, lpar=args.lpar, uuid=lparUUID, targetFrame=elem[0])
        log.debug('Demarrage [' + thread_LPM.getName() + '] ')
        thread_LPM.start()
        threads.append(thread_LPM)
    #-------------------------------------------------------------------
    # la même chose mais vers des frames gérées par d'autres HMC...
    ##-------------------------------------------------------------------
    else:
        thread_LPM = doLPMValidateJob(log, hmc=result["hmc1"], token=token, lpar=args.lpar, uuid=lparUUID, targetFrame=elem[0], targetHMC=elem[1])
        log.debug('Demarrage [' + thread_LPM.getName()+ '] ')
        thread_LPM.start()
        threads.append(thread_LPM)

### processing results
#for t in threads:
#    t.join()
#    resultLPM = t.getResult()
#    log.info('Result Thread : ' + resultLPM)
