import os
import urllib
from collections import namedtuple
from posixpath import normpath


__version__ = '0.2.2'

__all__ = ['URL', 'SplitResult', 'parse', 'extract', 'construct', 'normalize',
           'normalize_host', 'normalize_path', 'normalize_query',
           'normalize_fragment', 'encode', 'unquote', 'split', 'split_netloc',
           'split_host']


PSL_URL = 'https://publicsuffix.org/list/effective_tld_names.dat'

def _get_public_suffix_list():
    """Return a set containing all Public Suffixes.

    If the env variable PUBLIC_SUFFIX_LIST does not point to a local copy of the
    public suffix list it is downloaded into memory each time urltools is
    imported.
    """
    local_psl = os.environ.get('PUBLIC_SUFFIX_LIST')
    if local_psl:
        with open(local_psl) as f:
            psl_raw = f.readlines()
    else:
        psl_raw = urllib.urlopen(PSL_URL).readlines()
    psl = set()
    for line in psl_raw:
        item = line.strip()
        if item != '' and not item.startswith('//'):
            psl.add(item)
    return psl

PSL = _get_public_suffix_list()


SCHEMES = ['http', 'https', 'ftp', 'sftp', 'file', 'gopher', 'imap', 'mms',
           'news', 'nntp', 'telnet', 'prospero', 'rsync', 'rtsp', 'rtspu',
           'svn', 'git', 'ws', 'wss']
SCHEME_CHARS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
IP_CHARS = '0123456789.:'
DEFAULT_PORT = {
    'http': '80',
    'https': '443',
    'ws': '80',
    'wss': '443',
    'ftp': '21',
    'sftp': '22'
}
QUOTE_EXCEPTIONS = {
    'path': ' /?+#',
    'query': ' &=+#',
    'fragment': ' +#'
}


SplitResult = namedtuple('SplitResult', ['scheme', 'netloc', 'path', 'query',
                                         'fragment'])
URL = namedtuple('URL', ['scheme', 'username', 'password', 'subdomain',
                         'domain', 'tld', 'port', 'path', 'query', 'fragment',
                         'url'])

_hextochr = {'%02x' % i: chr(i) for i in range(256)}
_hextochr.update({'%02X' % i: chr(i) for i in range(256)})


def _idna_encode(x):
    return x.decode('utf-8').encode('idna')


def _idna_decode(x):
    return x.decode('idna').encode('utf-8')


def normalize(url):
    """Normalize a URL.

    >>> normalize('hTtp://ExAMPLe.COM:80')
    'http://example.com/'
    """
    if url.strip() == '':
        return ''
    parts = split(url.strip())
    if parts.scheme:
        netloc = parts.netloc
        if parts.scheme in SCHEMES:
            path = normalize_path(parts.path)
        else:
            path = parts.path
    else:
        netloc = parts.path
        path = ''
        if '/' in netloc:
            netloc, path_raw = netloc.split('/', 1)
            path = normalize_path('/' + path_raw)
    username, password, host, port = split_netloc(netloc)
    host = normalize_host(host)
    port = _normalize_port(parts.scheme, port)
    query = normalize_query(parts.query)
    fragment = normalize_fragment(parts.fragment)
    return construct(URL(parts.scheme, username, password, None, host, None,
                         port, path, query, fragment, None))


def encode(url):
    """Encode URL."""
    parts = extract(url)
    return construct(URL(parts.scheme,
                         parts.username,
                         parts.password,
                         _idna_encode(parts.subdomain),
                         _idna_encode(parts.domain),
                         _idna_encode(parts.tld),
                         parts.port,
                         urllib.quote(parts.path),
                         urllib.quote(parts.query),
                         urllib.quote(parts.fragment),
                         None))


def construct(parts):
    """Construct a new URL from parts."""
    nurl = ''
    if parts.scheme:
        if parts.scheme in SCHEMES:
            nurl += parts.scheme + '://'
        else:
            nurl += parts.scheme + ':'
    if parts.username and parts.password:
        nurl += parts.username + ':' + parts.password + '@'
    elif parts.username:
        nurl += parts.username + '@'
    if parts.subdomain:
        nurl += parts.subdomain + '.'
    nurl += parts.domain
    if parts.tld:
        nurl += '.' + parts.tld
    if parts.port:
        nurl += ':' + parts.port
    if parts.path:
        nurl += parts.path
    if parts.query:
        nurl += '?' + parts.query
    if parts.fragment:
        nurl += '#' + parts.fragment
    return nurl


def normalize_host(host):
    """Normalize host (decode IDNA)."""
    if 'xn--' not in host:
        return host
    return '.'.join([_idna_decode(p) for p in host.split('.')])


def _normalize_port(scheme, port):
    """Return port if it is not default port, else None.

    >>> _normalize_port('http', '80')

    >>> _normalize_port('http', '8080')
    '8080'
    """
    assert type(port) == str
    if not scheme:
        return port
    if port and port != DEFAULT_PORT[scheme]:
        return port


def normalize_path(path):
    """Normalize path: collapse etc.

    >>> normalize_path('/a/b///c')
    '/a/b/c'
    """
    if path in ['//', '/', '']:
        return '/'
    npath = normpath(unquote(path, exceptions=QUOTE_EXCEPTIONS['path']))
    if path[-1] == '/' and npath != '/':
        npath += '/'
    return npath


def normalize_query(query):
    """Normalize query: sort params by name, remove params without value.

    >>> normalize_query('z=3&y=&x=1')
    'x=1&z=3'
    """
    if query == '' or len(query) <= 2:
        return ''
    nquery = unquote(query, exceptions=QUOTE_EXCEPTIONS['query'])
    params = nquery.split('&')
    nparams = []
    for param in params:
        if '=' in param:
            k, v = param.split('=', 1)
            if k and v:
                nparams.append("%s=%s" % (k, v))
    nparams.sort()
    return '&'.join(nparams)


def normalize_fragment(fragment):
    """Normalize fragment (unquote with exceptions only)"""
    return unquote(fragment, QUOTE_EXCEPTIONS['fragment'])


def unquote(text, exceptions=[]):
    """Unquote a text but ignore the exceptions.

    >>> unquote('foo%23bar')
    'foo#bar'
    >>> unquote('foo%23bar', ['#'])
    'foo%23bar'
    """
    if not text:
        if text is None:
            raise TypeError('None object cannot be unquoted')
        else:
            return text
    if '%' not in text:
        return text
    s = text.split('%')
    res = [s[0]]
    for h in s[1:]:
        c = _hextochr.get(h[:2])
        if c and c not in exceptions:
            if len(h) > 2:
                res.append(c + h[2:])
            else:
                res.append(c)
        else:
            res.append('%' + h)
    return ''.join(res)


def parse(url):
    """Parse a URL.

    >>> parse('http://example.com/foo/')
    URL(scheme='http', ..., domain='example', tld='com', ..., path='/foo/', ...)
    """
    parts = split(url)
    if parts.scheme:
        username, password, host, port = split_netloc(parts.netloc)
        subdomain, domain, tld = split_host(host)
    else:
        username = password = subdomain = domain = tld = port = ''
    return URL(parts.scheme, username, password, subdomain, domain, tld,
               port, parts.path, parts.query, parts.fragment, url)


def extract(url):
    """Extract as much information from a (relative) URL as possible.

    >>> extract('example.com/abc')
    URL(..., domain='example', tld='com', ..., path='/abc', ...)
    """
    parts = split(url)
    if parts.scheme:
        netloc = parts.netloc
        path = parts.path
    else:
        netloc = parts.path
        path = ''
        if '/' in netloc:
            netloc, path_raw = netloc.split('/', 1)
            path = '/' + path_raw
    username, password, host, port = split_netloc(netloc)
    subdomain, domain, tld = split_host(host)
    return URL(parts.scheme, username, password, subdomain, domain, tld,
               port, path, parts.query, parts.fragment, url)


def split(url):
    """Split URL into scheme, netloc, path, query and fragment.

    >>> split('http://www.example.com/abc?x=1&y=2#foo')
    SplitResult(scheme='http', netloc='www.example.com', path='/abc', query='x=1&y=2', fragment='foo')
    """
    scheme = netloc = path = query = fragment = ''
    ip6_start = url.find('[')
    scheme_end = url.find(':')
    if ip6_start > 0 and ip6_start < scheme_end:
        scheme_end = -1
    if scheme_end > 0:
        for c in url[:scheme_end]:
            if c not in SCHEME_CHARS:
                break
        else:
            scheme = url[:scheme_end].lower()
            rest = url[scheme_end:].lstrip(':/')
    if not scheme:
        rest = url
    l_path = rest.find('/')
    l_query = rest.find('?')
    l_frag = rest.find('#')
    if l_path > 0:
        if l_query > 0 and l_frag > 0:
            netloc = rest[:l_path]
            path = rest[l_path:min(l_query, l_frag)]
        elif l_query > 0:
            if l_query > l_path:
                netloc = rest[:l_path]
                path = rest[l_path:l_query]
            else:
                netloc = rest[:l_query]
                path = ''
        elif l_frag > 0:
            netloc = rest[:l_path]
            path = rest[l_path:l_frag]
        else:
            netloc = rest[:l_path]
            path = rest[l_path:]
    else:
        if l_query > 0:
            netloc = rest[:l_query]
        elif l_frag > 0:
            netloc = rest[:l_frag]
        else:
            netloc = rest
    if l_query > 0:
        if l_frag > 0:
            query = rest[l_query+1:l_frag]
        else:
            query = rest[l_query+1:]
    if l_frag > 0:
        fragment = rest[l_frag+1:]
    if not scheme:
        path = netloc + path
        netloc = ''
    return SplitResult(scheme, netloc, path, query, fragment)


def _clean_netloc(netloc):
    """Remove trailing '.' and ':' and tolower

    >>> _clean_netloc('eXample.coM:')
    'example.com'
    """
    try:
        netloc.encode('ascii')
    except:
        return netloc.rstrip('.:').decode('utf-8').lower().encode('utf-8')
    else:
        return netloc.rstrip('.:').lower()


def split_netloc(netloc):
    """Split netloc into username, password, host and port.

    >>> split_netloc('foo:bar@www.example.com:8080')
    ('foo', 'bar', 'www.example.com', '8080')
    """
    username = password = host = port = ''
    if '@' in netloc:
        user_pw, netloc = netloc.split('@', 1)
        if ':' in user_pw:
            username, password = user_pw.split(':', 1)
        else:
            username = user_pw
    netloc = _clean_netloc(netloc)
    if ':' in netloc and netloc[-1] != ']':
        host, port = netloc.rsplit(':', 1)
    else:
        host = netloc
    return username, password, host, port


def split_host(host):
    """Use the Public Suffix List to split host into subdomain, domain and tld.

    >>> split_host('foo.bar.co.uk')
    ('foo', 'bar', 'co.uk')
    """
    # host is IPv6?
    if '[' in host:
        return '', host, ''
    # host is IPv4?
    for c in host:
        if c not in IP_CHARS:
            break
    else:
        return '', host, ''
    # host is a domain name
    domain = subdomain = tld = ''
    parts = host.split('.')
    for i in range(len(parts)):
        tld = '.'.join(parts[i:])
        wildcard_tld = '*.' + tld
        exception_tld = '!' + tld
        if exception_tld in PSL:
            domain = '.'.join(parts[:i+1])
            tld = '.'.join(parts[i+1:])
            break
        if tld in PSL:
            domain = '.'.join(parts[:i])
            break
        if wildcard_tld in PSL:
            domain = '.'.join(parts[:i-1])
            tld = '.'.join(parts[i-1:])
            break
    if '.' in domain:
        subdomain, domain = domain.rsplit('.', 1)
    return subdomain, domain, tld
