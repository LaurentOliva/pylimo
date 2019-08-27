<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0" 
	xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
	xmlns:ns2="http://a9.com/-/spec/opensearch/1.1/"
	xmlns:ns3="http://www.w3.org/1999/xhtml"
	>
	<xsl:output method="html" indent="yes" encoding="utf-8"/>
	<xsl:template match="*[local-name() = 'entry']">
    <html>
		<head>
			<title>LPM Validate Job result</title> 
				<link href="/plugin/configuration_des_serveurs/Getconfig/design/design.css" type="text/css" rel="stylesheet" />				
				<!--style media="lpm_output" type="text/css"-->
				<style>
						
				table, th, td {
					border: 1px solid black;
					border-collapse: collapse;
					font-family: "Courrier New", courier, sans-serif;
				}
				th, td {
					padding: 3px;
					text-align: left;
				}
				table#t01 tr:nth-child(even) {
					background-color: #eee;
				}
				table#t01 tr:nth-child(odd) {
					background-color:#fff;
				}
				table#t01 th	{
					background-color: red;
					color: white;
				}
				body {
				
				font-family: Arial, Inconsolata, monospace, "Liberation Mono", Consolas, Courier, monospace;
				
				}
				</style>				
		</head>
	<body>
		<h2>
		<u>LPM Validate Job Result </u>:
		<xsl:value-of select="//*[local-name() = 'Status']"/>
		<br/>
		</h2>
		<hr/>
		
		<b> Date :	
		<xsl:call-template name="formatDate">
			<xsl:with-param name="dateTime" select="//*[local-name() = 'published']" />
		</xsl:call-template>
		</b>
		<br/>

		<b> Time :	
		<xsl:call-template name="formatTime">
			<xsl:with-param name="dateTime" select="//*[local-name() = 'published']" />
		</xsl:call-template>
		</b>
		<br/>
		
		<b> Timezone : UTC+	
		<xsl:call-template name="formatTimezone">
			<xsl:with-param name="Timezone" select="//*[local-name() = 'published']" />
		</xsl:call-template>
		</b>
		<br/>
		
		<hr/>		
				<h2><u>Job Parameters</u></h2>

		<table id="t01" >
		<thead>
			<tr>
				<th>Name</th>
				<th>Value</th>
			</tr>
		</thead>
		
		<xsl:for-each select="//*[local-name() = 'link'][@rel = 'MANAGEMENT_CONSOLE']">
				<tr>
				<td>
				<xsl:text> HMC Source </xsl:text>
				</td>
				<td>
				<xsl:if test="starts-with(@href, 'https://')">
						<xsl:call-template name="getHMCName">
								<xsl:with-param name="URL" select="@href" />
						</xsl:call-template>
				</xsl:if>
				</td>
				</tr>
		</xsl:for-each>		
	
		<xsl:for-each select="//*[local-name() = 'JobParameters']/*[local-name() = 'JobParameter']">
			<tr>
			<td><xsl:value-of select="*[local-name() = 'ParameterName']"/></td>
			<td><xsl:value-of select="*[local-name() = 'ParameterValue']"/></td>
			</tr>		
		</xsl:for-each>
		
			<tr>
			<td>Job duration</td>
			<td>
				<xsl:variable name="timeStarted" select="//*[local-name() = 'TimeStarted']" /> 
				<xsl:variable name="timeCompleted" select="//*[local-name() = 'TimeCompleted']" /> 
				<xsl:value-of select="($timeCompleted - $timeStarted) div 1000" />
				seconds
			</td>
			</tr>
			
			<tr>
			<td> Job ID </td>
			<td> <xsl:value-of select="//*[local-name() = 'JobID']"/> </td>
			</tr>
			
			<xsl:for-each select="//*[local-name() = 'Results']/*[local-name() = 'JobParameter']">
				<xsl:if test="*[local-name() = 'ParameterName' and text()='returnCode']">
					<tr>
					<td><xsl:value-of select="*[local-name() = 'ParameterName']"/></td>
					<td><xsl:value-of select="*[local-name() = 'ParameterValue']"/></td>
					</tr>
				</xsl:if>		
			</xsl:for-each>		
		</table>

		<xsl:for-each select="//*[local-name() = 'Results']/*[local-name() = 'JobParameter']">
			<pre>
				<xsl:if test="*[local-name() = 'ParameterName' and text()='result']">
					<xsl:value-of select="*[local-name() = 'ParameterValue']"/>
				</xsl:if>
			</pre>			
		</xsl:for-each>		

	</body>
    </html>
	</xsl:template>

	<xsl:template name="getHMCName">
		<xsl:param name="URL" />
		<xsl:variable name="hmcL" select="substring-after($URL, ':')" />
		<xsl:variable name="hmcM" select="substring-after($hmcL, '//')" />
		<xsl:variable name="hmc" select="substring-before($hmcM, ':')" />
		<xsl:value-of select="$hmc" />
	</xsl:template>
	
	<xsl:template name="formatDate">
		<xsl:param name="dateTime" />
		<xsl:variable name="date" select="substring-before($dateTime, 'T')" />
		<xsl:variable name="year" select="substring-before($date, '-')" />
		<xsl:variable name="month" select="substring-before(substring-after($date, '-'), '-')" />
		<xsl:variable name="day" select="substring-after(substring-after($date, '-'), '-')" />
		<xsl:value-of select="concat($day, '/', $month, '/', $year)" />
	</xsl:template>

	<xsl:template name="formatTime">
		<xsl:param name="dateTime" />
		<xsl:variable name="time" select="substring-after($dateTime, 'T')" />
		<xsl:variable name="time2" select="substring-before($time, '+')" />
		<xsl:value-of select="$time2" />
	</xsl:template>
	
	<xsl:template name="formatTimezone">
		<xsl:param name="Timezone" />
		<xsl:variable name="timezone" select="substring-after($Timezone, '+')" />
		<xsl:value-of select="$timezone" />
	</xsl:template>

</xsl:stylesheet>