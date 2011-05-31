#***************************************************************************
# pywbemdb - A DB API v2.0 compatible interface to WBEM.
# Copyright (C) 2011 Egor Puzanov.
#
#***************************************************************************
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA  02110-1301  USA
#***************************************************************************

__author__ = "Egor Puzanov"
__version__ = '2.0.0'

from xml.sax import handler, make_parser
import urllib2, base64
from datetime import datetime, timedelta
import threading
import re
WQLPAT = re.compile("^\s*SELECT\s+(?P<props>.+)\s+FROM\s+(?P<cn>\S+)(?:\s+WHERE\s+(?P<kbs>.+))?", re.I)
ANDPAT = re.compile("\s+AND\s+", re.I)
DTPAT = re.compile(r'^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})\.(\d{6})([+|-]\d{3})')
TDPAT = re.compile(r'^(\d{8})(\d{2})(\d{2})(\d{2})\.(\d{6})')


XML_REQ = """<CIM CIMVERSION="2.0" DTDVERSION="2.0">
<MESSAGE ID="1001" PROTOCOLVERSION="1.0">
<SIMPLEREQ>
<IMETHODCALL NAME="%s">
<LOCALNAMESPACEPATH>
<NAMESPACE NAME="%s"/>
</LOCALNAMESPACEPATH>%s
</IMETHODCALL>
</SIMPLEREQ>
</MESSAGE>
</CIM>"""
EXECQUERY_IPARAM = """
<IPARAMVALUE NAME="Query">
<VALUE>%s</VALUE>
</IPARAMVALUE>
<IPARAMVALUE NAME="QueryLanguage">
<VALUE>%s</VALUE>
</IPARAMVALUE>"""
CLNAME_IPARAM = """
<IPARAMVALUE NAME="ClassName">
<CLASSNAME NAME="%s"/>
</IPARAMVALUE>"""
QUALS_IPARAM = """
<IPARAMVALUE NAME="IncludeQualifiers">
<VALUE>%s</VALUE>
</IPARAMVALUE>
<IPARAMVALUE NAME="LocalOnly">
<VALUE>FALSE</VALUE>
</IPARAMVALUE>"""
PL_IPARAM = """
<IPARAMVALUE NAME="PropertyList">
<VALUE.ARRAY>
<VALUE>%s</VALUE>
</VALUE.ARRAY>
</IPARAMVALUE>"""

CIM_EMPTY=0
CIM_SINT8=16
CIM_UINT8=17
CIM_SINT16=2
CIM_UINT16=18
CIM_SINT32=3
CIM_UINT32=19
CIM_SINT64=20
CIM_UINT64=21
CIM_REAL32=4
CIM_REAL64=5
CIM_BOOLEAN=11
CIM_STRING=8
CIM_DATETIME=101
CIM_REFERENCE=102
CIM_CHAR16=103
CIM_OBJECT=13
CIM_FLAG_ARRAY=0x2000
CIM_ARR_SINT8=CIM_FLAG_ARRAY|CIM_SINT8
CIM_ARR_UINT8=CIM_FLAG_ARRAY|CIM_UINT8
CIM_ARR_SINT16=CIM_FLAG_ARRAY|CIM_SINT16
CIM_ARR_UINT16=CIM_FLAG_ARRAY|CIM_UINT16
CIM_ARR_SINT32=CIM_FLAG_ARRAY|CIM_SINT32
CIM_ARR_UINT32=CIM_FLAG_ARRAY|CIM_UINT32
CIM_ARR_SINT64=CIM_FLAG_ARRAY|CIM_SINT64
CIM_ARR_UINT64=CIM_FLAG_ARRAY|CIM_UINT64
CIM_ARR_REAL32=CIM_FLAG_ARRAY|CIM_REAL32
CIM_ARR_REAL64=CIM_FLAG_ARRAY|CIM_REAL64
CIM_ARR_BOOLEAN=CIM_FLAG_ARRAY|CIM_BOOLEAN
CIM_ARR_STRING=CIM_FLAG_ARRAY|CIM_STRING
CIM_ARR_DATETIME=CIM_FLAG_ARRAY|CIM_DATETIME
CIM_ARR_REFERENCE=CIM_FLAG_ARRAY|CIM_REFERENCE
CIM_ARR_CHAR16=CIM_FLAG_ARRAY|CIM_CHAR16
CIM_ARR_OBJECT=CIM_FLAG_ARRAY|CIM_OBJECT
CIM_ILLEGAL=0xfff
CIM_TYPEMASK=0x2FFF

class DBAPITypeObject:
    def __init__(self,*values):
        self.values = values
    def __cmp__(self,other):
        if other in self.values:
            return 0
        if other < self.values:
            return 1
        else:
            return -1

def Date(*args):
    """
    This function constructs an object holding a date value.
    """
    return "%04d%02d%02d000000.000000+000"%args

def Time(*args):
    """
    This function constructs an object holding a time value.
    """
    return "00000000%02d%02d%02d.000000:000"%args

def Timestamp(*args):
    """
    This function constructs an object holding a time stamp value.
    """
    return "%04d%02d%02d%02d%02d%02d.000000+000"%args

def DateFromTicks(ticks):
    """
    This function constructs an object holding a date value from the given
    ticks value.
    """
    return Date(*datetime.fromtimestamp(ticks).timetuple()[:3])

def TimeFromTicks(ticks):
    """
    This function constructs an object holding a time value from the given
    ticks value.
    """
    return Time(*datetime.fromtimestamp(ticks).timetuple()[3:6])

def TimestampFromTicks(ticks):
    """
    This function constructs an object holding a time stamp value from the
    given ticks value.
    """
    return Timestamp(*datetime.fromtimestamp(ticks).timetuple()[:6])

def Binary(string):
    """
    This function constructs an object capable of holding a binary (long)
    string value.
    """
    from array import array
    return array('c', x)

STRING = DBAPITypeObject(CIM_STRING, CIM_REFERENCE, CIM_CHAR16, CIM_OBJECT,
                         CIM_BOOLEAN)
BINARY = DBAPITypeObject(CIM_ARR_SINT8, CIM_ARR_UINT8, CIM_ARR_SINT16,
                        CIM_ARR_UINT16, CIM_ARR_SINT32, CIM_ARR_UINT32,
                        CIM_ARR_SINT64, CIM_ARR_UINT64, CIM_ARR_REAL32,
                        CIM_ARR_REAL64, CIM_ARR_BOOLEAN, CIM_ARR_STRING,
                        CIM_ARR_DATETIME, CIM_ARR_REFERENCE, CIM_ARR_CHAR16,
                        CIM_ARR_OBJECT)
NUMBER = DBAPITypeObject(CIM_SINT8, CIM_UINT8, CIM_SINT16, CIM_UINT16,
                        CIM_SINT32, CIM_UINT32, CIM_SINT64, CIM_UINT64,
                        CIM_REAL32, CIM_REAL64)
DATETIME = DBAPITypeObject(CIM_DATETIME)
ROWID = DBAPITypeObject()


### module constants

# compliant with DB SIG 2.0
apilevel = '2.0'

# module may be shared, but not connections
threadsafety = 2

# this module use extended python format codes
paramstyle = 'qmark'

### exception hierarchy

class Warning(StandardError):
    pass

class Error(StandardError):
    pass

class InterfaceError(Error):
    pass

class DatabaseError(Error):
    pass

class DataError(DatabaseError):
    pass

class OperationalError(DatabaseError):
    pass

class IntegrityError(DatabaseError):
    pass

class InternalError(DatabaseError):
    pass

class ProgrammingError(DatabaseError):
    pass

class NotSupportedError(DatabaseError):
    pass


### xml.sax content handler

class CIMHandler(handler.ContentHandler):

    def __init__(self, cursor):
        handler.ContentHandler.__init__(self)
        self._in=['IRETURNVALUE','IMETHODRESPONSE','SIMPLERSP','MESSAGE','CIM']
        self._cur = cursor
        self._qName = ''
        self._pName = ''
        self._pType = ''
        self._pVal = None
        self._pdict = {}
        self._kbs = []
        self._maxlen = {}

    def _datetime(self, dtarg):
        """
        Convert string to datetime.
        """
        s = DTPAT.match(dtarg)
        if s is not None:
            tt = map(int, s.groups(0))
            return datetime(*tt[:7]) - timedelta(minutes=tt[7])
        s = TDPAT.match(dtarg)
        if s is None: return str(dtarg)
        return timedelta(**dict(zip(('days','hours','minutes','microseconds'),
                                                        map(int, s.groups(0)))))

    def _parseType(self, ptype):
        """
        Return type number and convert function.
        """
        return {
            'uint8': (CIM_UINT8, int),
            'uint16': (CIM_UINT16, int),
            'uint32': (CIM_UINT32, int),
            'uint64': (CIM_UINT64, long),
            'sint8': (CIM_SINT8, int),
            'sint16': (CIM_SINT16, int),
            'sint32': (CIM_SINT32, int),
            'sint64': (CIM_SINT64, long),
            'real32': (CIM_REAL32, float),
            'real64': (CIM_REAL64, float),
            'string': (CIM_STRING, str),
            'char16': (CIM_CHAR16, str),
            'object': (CIM_OBJECT, str),
            'reference': (CIM_REFERENCE, str),
            'boolean': (CIM_BOOLEAN, (lambda val: val.lower() is 'true')),
            'datetime': (CIM_DATETIME, self._datetime),
        }.get(ptype, (CIM_STRING, str))

    def startElement(self, name, attrs):
        if name in ('PROPERTY.REFERENCE', 'VALUE.ARRAY', 'VALUE.REFERENCE',
            'VALUE'): return
        if self._in:
            tag = self._in.pop()
            if name == tag:
                if name != 'IMETHODRESPONSE' or str(attrs._attrs.get('NAME',
                                        '')) == self._cur._methodname: return
                raise InterfaceError(0, 'Expecting attribute NAME=%s, got %s'%(
                    self._cur._methodname, str(attrs._attrs.get('NAME', ''))))
            elif name == 'ERROR':
                errcode = int(attrs._attrs.get('CODE', 0))
                raise InterfaceError(errcode, attrs._attrs.get('DESCRIPTION',
                            'Error code %s'%errcode))
            else:
                raise InterfaceError(0,'Expecting %s element, got %s'%(tag,name))
#        elif name == 'QUALIFIER':
#            self._qName = str(attrs._attrs.get('NAME', ''))
        elif name == 'PROPERTY':
            self._pName = str(attrs._attrs.get('NAME', ''))
            self._pType = str(attrs._attrs.get('TYPE', 'string'))
            self._pVal = None
            if type(self._cur.description) is tuple: return
            self._cur.description.append((self._pName,
                self._parseType(self._pType)[0], None, None, None, None, None))
        elif name == 'PROPERTY.ARRAY':
            self._pName = str(attrs._attrs.get('NAME', ''))
            self._pType = str(attrs._attrs.get('TYPE', 'string'))
            self._pVal = []
            if type(self._cur.description) is tuple: return
            self._cur.description.append((self._pName,
                0x2000|self._parseType(self._pType)[0],None,None,None,None,None))
        elif name == 'KEYVALUE':
            self._pType = str(attrs._attrs.get('VALUETYPE', 'string'))
        elif name == 'KEYBINDING':
            self._pName = str(attrs._attrs.get('NAME', ''))
        elif name == 'INSTANCE':
            if not self._cur.description: self._cur.description = []
        elif name == 'INSTANCENAME':
            self._pdict['__CLASS'] = str(attrs._attrs.get('CLASSNAME', ''))
            self._pdict['__NAMESPACE'] = self._cur.connection._namespace


    def characters(self, content):
        if not content.strip(): return
        if content == 'NULL': val = None
        else:
            try: val = self._parseType(self._pType)[1](content)
            except ValueError: val = unicode(content)
        if type(self._pVal) is list: self._pVal.append(val)
        else: self._pVal = val


    def endElement(self, name):
        if name in ('PROPERTY.REFERENCE', 'VALUE.ARRAY', 'VALUE.REFERENCE',
            'VALUE', 'KEYVALUE'): return
#        if name == 'QUALIFIER':
#            if self._qName == 'Key' and self._pVal.upper() == 'TRUE':
#                self._cur._keybindings[self._pName] = self._pType
#            elif self._qName == 'MaxLen':
#                self._maxlen[self._pName] = int(self._pVal)
        if name == 'PROPERTY':
            self._pdict[self._pName.upper()] = self._pVal
        elif name == 'PROPERTY.ARRAY':
            self._pdict[self._pName.upper()] = self._pVal
            self._pVal = None
        elif name == 'KEYBINDING':
            if self._pType == 'string':
                self._kbs.append('%s="%s"'%(self._pName, self._pVal))
            else:
                self._kbs.append('%s=%s'%(self._pName, self._pVal))
        elif name == 'INSTANCE':
            if type(self._cur.description) is list:
                if self._cur._props:
                    pDct=dict([(p[0].upper(),p) for p in self._cur.description])
                    self._cur.description = [pDct.get(p.upper(), (p, CIM_STRING,
                        None,None,None,None,None)) for p in self._cur._props]
                else:self._cur.description.extend([(p,CIM_STRING,None,None,None,
                    None,None) for p in ['__CLASS', '__NAMESPACE', '__PATH']])
                self._cur.description = tuple(self._cur.description)
            for pname, kbval in self._cur._keybindings.iteritems():
                pval = self._pdict.get(pname.upper(), '')
                if kbval == pval: continue
                self._pdict.clear()
                return
            self._cur._rows.append(tuple([self._pdict.get(
                        p[0].upper(), None) for p in self._cur.description]))
            self._pdict.clear()
        elif name == 'INSTANCENAME':
            self._pdict['__PATH'] = '%s.%s'%(self._pdict['__CLASS'],
                                            ','.join(self._kbs))
            del self._kbs[:]


### cursor object

class wbemCursor(object):
    """
    This class emulate a database cursor, which is used to issue queries
    and fetch results from a WBEM connection.
    """

    def __init__(self, connection):
        """
        Initialize a Cursor object. connection is a wbemCnx object instance.
        """
        self.connection = connection
        self.description = None
        self.rownumber = -1
        self.arraysize = 1
        self._rows = []
        self._props = []
        self._keybindings = {}
        self._methodname = ''
        self._parser = make_parser()
        self._parser.setContentHandler(CIMHandler(self))

    @property
    def rowcount(self):
        """
        Returns number of rows affected by last operation. In case
        of SELECTs it returns meaningful information only after
        all rows has been fetched.
        """
        return len(self._rows)

    def _check_executed(self):
        if not self.connection:
            raise InterfaceError, "Connection closed."
        if not self.description:
            raise OperationalError, "No data available. execute() first."

    def __del__(self):
        self.close()

    def close(self):
        """
        Closes the cursor. The cursor is unusable from this point.
        """
        self.description = None
        self.connection = None
        self._parser = None

    def execute(self, operation, *args):
        """
        Prepare and execute a database operation (query or command).
        Parameters may be provided as sequence or mapping and will be
        bound to variables in the operation. Parameter style for WSManDb
        is %-formatting, as in:
        cur.execute('select * from table where id=%d', id)
        cur.execute('select * from table where strname=%s', name)
        Please consult online documentation for more examples and
        guidelines.
        """
        if not self.connection:
            raise InterfaceError, "Connection closed."
        self.description = None
        self.rownumber = -1
        del self._rows[:]

        # for this method default value for params cannot be None,
        # because None is a valid value for format string.

        if (args != () and len(args) != 1):
            raise TypeError, "execute takes 1 or 2 arguments (%d given)" % (len(args) + 1,)

        if args != ():
            operation = operation%args[0]

        try:
            self.connection._execute(self, operation)
            if self.description: self.rownumber = 0

        except OperationalError, e:
            raise OperationalError, e
        except InterfaceError, e:
            raise InterfaceError, e

    def executemany(self, operation, param_seq):
        """
        Execute a database operation repeatedly for each element in the
        parameter sequence. Example:
        cur.executemany("INSERT INTO table VALUES(%s)", [ 'aaa', 'bbb' ])
        """
        for params in param_seq:
            self.execute(operation, params)

    def nextset(self):
        """
        This method makes the cursor skip to the next available result set,
        discarding any remaining rows from the current set. Returns true
        value if next result is available, or None if not.
        """
        self._check_executed()
        return None

    def fetchone(self):
        """Fetches a single row from the cursor. None indicates that
        no more rows are available."""
        self._check_executed()
        return self.connection._fetchone(self)

    def fetchmany(self, size=None):
        """Fetch up to size rows from the cursor. Result set may be smaller
        than size. If size is not defined, cursor.arraysize is used."""
        self._check_executed()
        if not size: size = self.arraysize
        results = []
        while size and row:
            results.append(row)
            size -= 1
            if size: row = self.connection._fetchone(self)
        return results

    def fetchall(self):
        """Fetchs all available rows from the cursor."""
        self._check_executed()
        results = []
        row = self.connection._fetchone(self)
        while row:
            results.append(row)
            row = self.connection._fetchone(self)
        return results

    def next(self):
        """Fetches a single row from the cursor. None indicates that
        no more rows are available."""
        row = self.connection._fetchone(self)
        if not row: raise StopIteration
        return row

    def __iter__(self):
        """
        Return self to make cursors compatible with
        Python iteration protocol.
        """
        self._check_executed()
        return self

    def setinputsizes(self, sizes=None):
        """
        This method does nothing, as permitted by DB-API specification.
        """
        self._check_executed()

    def setoutputsize(self, size=None, column=0):
        """
        This method does nothing, as permitted by DB-API specification.
        """
        self._check_executed()

### connection object

class pywbemCnx:
    """
    This class represent an WBEM Connection connection.
    """
    def __init__(self, *args, **kwargs):
        self._lock = threading.RLock()
        self._host = kwargs.get('host', 'localhost')
        self._creds = (kwargs.get('user', ''), kwargs.get('password', ''))
        self._scheme = kwargs.get('scheme', 'https')
        self._port=int(kwargs.get('port',self._scheme=='http' and 5988 or 5989))
        self._namespace = kwargs.get('namespace', 'root/cimv2')
        self._x509 = kwargs.get('x509', {})
        self._dialect = kwargs.get('dialect', '').upper()
        self._url='%s://%s:%s/cimom'%(self._scheme,self._host,self._port)

    def _wbem_request(self, methodname, data):
        """Send XML data over HTTP to the specified url. Return the
        response in XML.  Uses Python's build-in urllib2.
        """

        data = '<?xml version="1.0" encoding="utf-8" ?>\n%s'%data

        headers = { 'Content-type': 'application/xml; charset="utf-8"',
                    'Content-length': len(data),
                    'CIMOperation': 'MethodCall',
                    'CIMMethod': methodname,
                    'CIMObject': self._namespace}

        if self._creds[0] is not '': 
            headers['Authorization'] = 'Basic %s'%base64.encodestring(
                                        '%s:%s'%self._creds).replace('\n', '')

        request = urllib2.Request(self._url, data, headers)

        tryLimit = 5
        while tryLimit:
            tryLimit -= 1
            try:
                xml_repl = urllib2.urlopen(request)
                return xml_repl
            except urllib2.HTTPError, arg:
                raise InterfaceError('HTTP error: %s' % arg.code)
            except urllib2.URLError, arg:
                if arg.reason[0] in [32, 104]: continue
                raise InterfaceError('socket error: %s' % arg.reason)
        if hasattr(arg, reason):
            raise InterfaceError('socket error: %s' % arg.reason)
        else:
            raise InterfaceError('HTTP error: %s' % arg.code)


    def _execute(self, cursor, query):
        """
        Execute Query
        """
        try:
            props, classname, where = WQLPAT.match(query).groups('')
        except:
            raise ProgrammingError, "Syntax error in the query statement."
        if props == '*': cursor._props = []
        else:cursor._props=[p for p in set(props.replace(' ','').split(','))]
        cursor._keybindings.clear()
        self._lock.acquire()
        try:
            try:
                if self._dialect:
                    method = 'ExecQuery'
                    cursor._methodname = method
                    xml_repl = self._wbem_request(method, XML_REQ%(method,
                        '"/>\n<NAMESPACE NAME="'.join(self._namespace.split('/')
                        ), EXECQUERY_IPARAM%(query, self._dialect)))
                else:
                    if where:
                        try: cursor._keybindings.update(
                            eval('(lambda **kws:kws)(%s)'%ANDPAT.sub(',',where))
                            )
                        except: raise OperationalError('Unsupported syntax.')
                    method = 'EnumerateInstances'
                    cursor._methodname = method
                    pLst = [p for p in cursor._props \
                        if p.upper() not in ('__PATH','__CLASS','__NAMESPACE')]
                    xml_repl = self._wbem_request(method, XML_REQ%(method,
                        '"/>\n<NAMESPACE NAME="'.join(self._namespace.split('/')
                        ),''.join((CLNAME_IPARAM%classname,QUALS_IPARAM%'FALSE',
                        pLst and PL_IPARAM%'</VALUE>\n<VALUE>'.join(pLst) or '')
                        )))
                cursor._parser.parse(xml_repl)
            except InterfaceError, e:
                raise InterfaceError, e
            except OperationalError, e:
                raise OperationalError, e
            except Exception, e:
                raise OperationalError, e
        finally:
            self._lock.release()

    def _fetchone(self, cursor):
        """Fetches a single row from the cursor rows cache. None indicates that
        no more rows are available."""
        if cursor._rows:
            cursor.rownumber += 1
            return cursor._rows.pop(0)
        else: return None

    def __del__(self):
        self.close()

    def close(self):
        """
        Close connection to the WBEM CIMOM. Implicitly rolls back
        """
        return

    def commit(self):
        """
        Commit transaction which is currently in progress.
        """
        return

    def rollback(self):
        """
        Roll back transaction which is currently in progress.
        """
        return

    def cursor(self):
        """
        Return cursor object that can be used to make queries and fetch
        results from the database.
        """
        return wbemCursor(self)

    def autocommit(self, status):
        """
        Turn autocommit ON or OFF.
        """
        return

# connects to a WBEM CIMOM
def Connect(*args, **kwargs):

    """
    Constructor for creating a connection to the WBEM. Returns
    a WBEM Connection object. Paremeters are as follows:

    scheme        http or https
    port          port
    user          user to connect as
    password      user's password
    host          host name
    namespace     namespace
    dialect       query dialect

    Examples:
    con  =  pywbemdb.connect(scheme='https',
                            port=5989,
                            user='user',
                            password='P@ssw0rd'
                            host='localhost',
                            namespace='root/cimv2',
                            dialect='CQL'
                            )
    """

    return pywbemCnx(*args, **kwargs)

connect = Connection = Connect

__all__ = [ 'BINARY', 'Binary', 'Connect', 'Connection', 'DATE',
    'Date', 'Time', 'Timestamp', 'DateFromTicks', 'TimeFromTicks',
    'TimestampFromTicks', 'DataError', 'DatabaseError', 'Error',
    'FIELD_TYPE', 'IntegrityError', 'InterfaceError', 'InternalError',
    'NULL', 'NUMBER', 'NotSupportedError', 'DBAPITypeObject',
    'OperationalError', 'ProgrammingError', 'ROWID', 'STRING', 'TIME',
    'TIMESTAMP', 'Warning', 'apilevel', 'connect', 'paramstyle','threadsafety']
