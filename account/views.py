import json
#import ldap

from django.shortcuts import render, render_to_response
from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.template import RequestContext
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import *
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse

from aglaia.settings import LOGIN_URL, ACCOUNT_HOME_URL, EMAIL_AUTH_PREFIX
from account.models import *
from account.interface import *
from aglaia.views import show_message
from aglaia.decorators import permission_required, method_required, http_denied, show_denied_message
from aglaia.messages import *
from aglaia.mail_tools import *
from log.interface import *

ldappath = "ldap://xxxx"#ldap服务器地址
baseDN = "DC=aaaa,DC=bbbb,DC=com"#根目录
ldapuser = "xxxx";#ldap服务器用户名
ldappass = "xxxx";#ldap服务器密码

normal_perms = [NORMAL]

manager_perms = [   GOODS_AUTH,
                    USER_AUTH,
                    VIEW_ALL,
                    MODF_NORMAL,
                    MODF_KEY,
                    COMPUT_AUTH]

super_perms = [ DEL_USER,
                MODF_PERM,
                MODF_GROUP]
perms_map = {'normal':normal_perms,
             'manager':manager_perms,
             'supervisor':super_perms}
#===============================================
#===============================================
#===============================================
#===============================================
#===============================================
#===============================================
# def ldap_add(username, password):
#     l = ldap.open(LDAP_HOST)
#     l.protocol_version = ldap.VERSION3
#     l.simple_bind(LDAP_BIND, LDAP_PASS)
#  
#     pw = password
#     addDN = "cn=%s,ou=People,dc=vpsee,dc=com" % cn
#     attrs = {}
#     attrs['objectclass'] = ['top','person','inetOrgPerson','posixAccount','vpseeAccount']
#     attrs['pw'] = pw
#     attrs['homeDirectory'] = '/home/people/%s' % username
#     attrs['loginShell'] = '/bin/bash'
#     attrs['uid'] = username
#     attrs['uidNumber'] = ldap_newuid()
#     attrs['gidNumber'] = ldap_getgid()
#     attrs['active'] = 'TRUE'
#     ldif = modlist.addModlist(attrs)
#     l.add_s(addDN, ldif)
#     l.unbind_s()
#  
# def ldap_getpw(username):
#     try:
#         l = ldap.open(LDAP_HOST)
#         l.protocol_version = ldap.VERSION3
#         l.simple_bind(LDAP_BIND, LDAP_PASS)
#  
#         searchScope = ldap.SCOPE_SUBTREE
#         searchFilter = "uid=*" + username + "*"
#         resultID = l.search(LDAP_BASE, searchScope, searchFilter, None)
#         result_set = []
#         while 1:
#             result_type, result_data = l.result(resultID, 0)
#             if (result_data == []):
#                 break
#             else:
#                 if result_type == ldap.RES_SEARCH_ENTRY:
#                     result_set.append(result_data)
#         return result_set[0][0][1]['pw'][0]
#     except ldap.LDAPError, e:
#         print e



def perm_checkname(perm):
    return APP_NAME+'.'+perm.codename

def add_perm(user, perm):
    user.user_permissions.add(perm)
    return

def rm_perm(user, perm):
    user.user_permissions.remove(perm)
    return

def add_group(user,groupname):
    g = Group.objects.get(name=groupname)
    user.groups.add(g)
    perms = perms_map[groupname]
    for pcode in perms:
        user.user_permissions.add(Permission.objects.get(codename=pcode))
    user.save()
    return

def rm_group(user,groupname):
    g = Group.objects.get(name=groupname)
    user.groups.remove(g)
    perms = perms_map[groupname]
    for pcode in perms:
        user.user_permissions.remove(Permission.objects.get(codename=pcode))
    user.save()
    return

def clear_groups(user):
    user.groups.clear()
    user.user_permissions.clear();
    return

def get_ordered_perms():
    p = Permission.objects.filter(content_type__model='account')
    p = p.exclude(name__endswith='account').order_by('codename')
    return p

def get_context_user(user):
    c_user = {}
    account = Account.objects.get(user=user)
    c_user['id'] = user.id
    c_user['username'] = user.username
    c_user['realname'] = account.real_name
    c_user['number'] = account.school_id
    try:
        user.groups.get(name='supervisor')
        c_user['type'] = 'supervisor'
    except Exception:
        try:
            user.groups.get(name='manager')
            c_user['type'] = 'manager'
        except Exception:
            c_user['type'] = 'normal'
    c_user['email'] = user.email
    c_user['email_verified'] = account.email_auth
    c_user['tel'] = account.tel
    depts = []
    for d in account.department.all():
        depts.append(d.depart_name)
    c_user['depts'] = depts
    perms = []
    allperm = get_ordered_perms()
    for p in allperm:
        if(user.has_perm(perm_checkname(p))):
            perms.append('1')
        else:
            perms.append('0')
    c_user['permissions'] = perms
    c_user['status'] = account.get_status_display()
    return c_user


def set_email_hash(account):
    import random,string
    account.email_hash = ''.join(random.sample(string.ascii_letters+string.digits, 30))
    account.save()
    return


#===============================================
#===============================================
#===============================================
#===============================================
#===============================================
#===============================================
def do_auth_email(request,username,ekey):
    # TODO
    try:
        account = Account.objects.get(user__username=username)
        if account.email_hash == ekey:
            account.email_auth = True
            account.save()
            return show_message(request,"Your Email has been authenticated! Welcome to Aglaia!")
    except:
        pass
    return show_message(request, 'Authenticate Email Failed!')

@method_required('POST')
def do_signin(request):
    """鎵ц鐧诲綍鎿嶄綔銆備娇鐢╬ost鏂规硶浼犻��'username'鍜�'password'銆�"""
    try:
        if request.user.is_authenticated():
            return HttpResponse('ok')
        else:
            post = dict(request.POST)
            try:
                username = post['username'][0]
                password = post['password'][0]
            except:
                return HttpResponse('mismatch')

            if not username or not password:
                return HttpResponse('mismatch')
#            if not password = ldap_getpw(password):
#                return HttpResponse('mismatch')
            user = authenticate(username=username, password=password)
            if not user or not user.is_active:
                return HttpResponse('mismatch')
            else:
                login(request, user)
                return HttpResponse('ok')
    except Exception as e:
        print(e)
        raise e


@method_required('POST')
def do_lookup_depts(request):
    """return the departments as a json:
        {
            'dept':['a','b',...]
        }
        query: 'keyword' """

    keyword = request.POST['keyword']
    depts = Department.objects.filter(depart_name__startswith=keyword)
    dep_list = []
    for dept in depts:
        dep_list.append(dept.depart_name)
    s = json.dumps({'depts':dep_list})
    return HttpResponse(s)

@method_required('POST')
def do_verify_username(request):
    """check if the user name is useble(correct format and not exist)"""
    try:
        username = request.POST['username']
        if not username or not check_style(username_regex, username):
            return HttpResponse('invalid')
        try:
            u = User.objects.get(username=username)
            if u:
                return HttpResponse('used')
        except Exception as e:
            print(e)
        return HttpResponse('ok')
    except Exception as e:
        print(e)
        raise e

@method_required('POST')
def do_signup(request):
    """鎵ц娉ㄥ唽鎿嶄綔銆備娇鐢╬ost鏂规硶浼犻��'username', 'realname','password'
    'email', 'departments', 'tel'銆�"""
    post = dict(request.POST)

    new_account = {}
    try:
        username = post['username'][0]
        if not check_style(username_regex, username):
            return HttpResponse('failed')
        new_account['user_name'] = username

        password = post['password'][0]
        if not check_style(password_regex, password):
            return HttpResponse('failed')
        new_account['password'] = password

        email = post['email'][0]
        if not check_email_style(email):
            return HttpResponse('failed')
        new_account['email'] = email

        realname = post['realname'][0]
        if not realname:
            return HttpResponse('failed')
        new_account['real_name'] = realname
        
        schid = post['number'][0]
        if not check_style(school_regex, schid):
           return HttpResponse('failed')
        new_account['school_id'] = schid

#        ldap_add(username, password)
    except Exception as e:
        print(e)
        return HttpResponse('failed')

    if 'tel' in post:
        tel = post['tel'][0]
        if not check_style(tel_regex, tel):
            return HttpResponse('failed')
        new_account['tel'] = tel

    depts = []
    if 'depts' in post:
        dept_string = post['depts'][0]
        if dept_string:
            depts = dept_string.split(',')
        new_account['department'] = depts


    new_account['status'] = status_unauth_key
    try:
        accounts = packed_create_user(request, [new_account])
        set_email_hash(accounts[0])
        send_auth_email(accounts[0])
        if not accounts:
            return HttpResponse('failed')
    except Exception as e:
        print(11)
        print(e)
    return HttpResponse('ok')

@method_required('POST')
@login_required
def do_modify_account(request):
    """鎵ц涓嶆晱鎰熺殑璐︽埛淇℃伅淇敼鎿嶄綔銆備娇鐢╬ost鏂规硶:'tel','depts','realname','number'銆�"""

    if not request.user.is_active:
        raise Http404
    post = request.POST
    content = {}
    if 'tel' in post:
        content['tel'] = post['tel']

    try:
        rname = post['realname']
        schid = post['number']
        if ( rname or schid ) and request.user.status != status_unauth_key and not request.user.has_perm(PERM_MODF_KEY):
            return HttpResponse('denied')
        if rname:
            content['real_name'] = rname
        if schid:
            content['school_id'] = schid
    except KeyError:
        pass
    try:
        packed_update_user(request, Account.objects.get(user=request.user).id, content, log=get_account_modif_log())
        return HttpResponse('ok')
    except Exception as e:
        print(e)
        return HttpResponse('invalid')


@method_required('POST')
@login_required
def do_modify_password(request):
    """鎵ц淇敼瀵嗙爜鎿嶄綔銆傛槸淇敼瀵嗙爜action锛屼娇鐢╬ost鏂规硶浼犻��'old_password'鍜�'new_password'銆�"""

    if not request.user.is_active:
        raise Http404
    user = request.user
    try:
        old_pass = request.POST['old_password']
        new_pass = request.POST['new_password']
        if user.check_password(old_pass):
            packed_update_user(request, Account.objects.get(user=request.user).id, {'password':new_pass}, log=get_pass_modif_log())
            return HttpResponse('ok')
        else:
            return HttpResponse('mismatch')
    except Exception as e:
        print(e)
        return HttpResponse('invalid')


@method_required('POST')
@login_required
def do_modify_email(request):
    """鎵ц淇敼鐢靛瓙閭欢鎿嶄綔锛屼娇鐢╬ost鏂规硶浼犻��'email'銆�"""

    if not request.user.is_active:
        raise Http404

    email = request.POST['email']
    if not check_email_style(email):
        return HttpResponse('invalid')

    request.user.email_auth = False
    request.user.email_hash = ''
    account = Account.objects.get(user=request.user)
    packed_update_user(request, account.id, {'email':email}, log=get_email_modif_log())
    set_email_hash(account)
    send_auth_email(account)
    return HttpResponse('ok')

@login_required
def do_logout(request):
    """璐﹀彿閫�鍑�"""
    logout(request)
    try:
        return HttpResponseRedirect(request.REQUEST['next'])
    except KeyError:
        return HttpResponseRedirect(LOGIN_URL)


@method_required('POST')
@permission_required(PERM_USER_AUTH, http_denied)
def do_approve_account(request):

    try:
        account = Account.objects.get(user__username=request.POST['username'])

        if not account or not account.user.is_active or account.status==status_destroy_key:
            return HttpResponse('denied')

        add_group(account.user, 'normal')
        packed_update_user(request, account.id, {'status':status_authed_key}, log=get_approve_account_log())

        return HttpResponse('ok')
    except:
        return HttpResponse('denied')

@method_required('POST')
@permission_required(PERM_USER_AUTH, http_denied)
def do_disapprove_account(request):
    try:
        account = Account.objects.get(user__username=request.POST['username'])
        if not account or not account.user.is_active or account.status==status_destroy_key:
            return HttpResponse('denied')
        clear_groups(account.user)
        packed_update_user(request, account.id, {'status':status_unauth_key}, log=get_disapprove_account_log())
        return HttpResponse('ok')
    except:
        return HttpResponse('denied')

@method_required('POST')
@permission_required(PERM_MODF_GROUP, http_denied)
def do_set_manager(request):

    try:
        account = Account.objects.get(user__username=request.POST['username'])
        if not account or not account.user.is_active or account.status==status_destroy_key:
            return HttpResponse('denied')

        add_group(account.user, 'manager')

        create_log('user', user_id = request.user.id,
        target=account, action='set manager',
        description=get_set_manager_log())

        return HttpResponse('ok')
    except:
        return HttpResponse('denied')

@method_required('POST')
@permission_required(PERM_MODF_GROUP, http_denied)
def do_clear_manager(request):
    try:
        account = Account.objects.get(user__username=request.POST['username'])
        if not account or not account.user.is_active or account.status==status_destroy_key:
            return HttpResponse('denied')

        rm_group(account.user, 'manager')

        create_log('user', user_id = request.user.id,
        target=account, action='remove manager',
        description=get_rm_manager_log())

        return HttpResponse('ok')
    except:
        return HttpResponse('denied')

@method_required('POST')
@permission_required(PERM_DEL_USER, http_denied)
def do_delete_account(request):
    try:
        account = Account.objects.get(user__username=request.POST['username'])
        if not account:
            return HttpResponse('denied')
        account.user.is_active = False
        packed_update_user(request, account.id, {'status':status_destroy_key}, log=get_delete_account_log())
        return HttpResponse('ok')
    except:
        return HttpResponse('denied')



def get_perm_denied(request):
    rst = {}
    rst['status'] = 'denied'
    rst['permissions'] = None
    return HttpResponse(json.dumps(rst))


@method_required('POST')
@permission_required(PERM_MODF_PERM, get_perm_denied)
def do_get_permissions(request):
    rst = {}
    try:
        account = Account.objects.get(user__username=request.POST['username'])
        if not account or not account.user.is_active or account.status==status_destroy_key:
            raise Exception
        perms = get_ordered_perms()
        user = account.user
        pdic = []
        for p in perms:
            if user.has_perm(perm_checkname(p)):
                pdic.append(1)
            else:
                pdic.append(0)
        rst['permissions'] = pdic
        rst['status'] = 'ok'
        return HttpResponse(json.dumps(rst))
    except:
        rst['status'] = 'denied'
        rst['permissions'] = None
    return HttpResponse(json.dumps(rst))


@method_required('POST')
@permission_required(PERM_MODF_PERM, http_denied)
def do_set_permissions(request):
    try:
        account = Account.objects.get(user__username=request.POST['username'])
        if not account or not account.user.is_active or account.status==status_destroy_key:
            return HttpResponse('denied')
        perms = get_ordered_perms()
        perm_set = request.POST['permissions']
        assert len(perms) == len(perm_set)
        user = account.user
        for i in range(0,len(perm_set)):
            if perm_set[i] == '1':
                add_perm(user, perms[i])
            else:
                rm_perm(user, perms[i])
        user.save()
        create_log('user', user_id = request.user.id,
        target=account, action='set permissions',
        description=get_set_perm_log(perms, perm_set))
        return HttpResponse('ok')
    except Exception as e:
        print(e)
        return HttpResponse('denied')

@method_required('POST')
@permission_required(PERM_VIEW_ALL)
def do_send_mail(request):
    try:
        id = request.POST['id']
        subj = request.POST['subject']
        msg = request.POST['message']
        acnt = Account.objects.get(user__id=id)
        send_user_mail(acnt, subj, msg)
        if 'next' in request.POST:
            return HttpResponseRedirect(request.POST['next'])
        return show_message(request, 'Send mail succeed!')
    except Exception as e:
        return show_message(request, 'Send mail failed: ' + e.__str__())





#===============================================
#===============================================
#===============================================
#===============================================
#===============================================
#===============================================

def show_signin(request):
    """鏄剧ず鐧诲綍椤甸潰銆�"""

    if request.user.is_authenticated():
        try:
            return HttpResponseRedirect(request.REQUEST['next'])
        except KeyError:
            return HttpResponseRedirect(ACCOUNT_HOME_URL)
    else:
        return render(request, 'signin.html')




@login_required
def account_home(request):
    # TODO
    return HttpResponseRedirect(reverse('goods.views.show_borrow'))


@method_required('GET')
@permission_required(PERM_VIEW_ALL)
def show_all_accounts(request):
    """鏄剧ず鎵�鏈夌敤鎴风殑鍒楄〃椤甸潰銆�"""

    unth = Account.objects.exclude(user__groups__name='normal')
    auth = Account.objects.filter(user__groups__name='normal')

    cont = {}

    cont['curpage'] = 'allaccounts'
    cont['num_accounts'] = 1
    cont['num_pages'] = 1
    cont['cur_index'] = 1

    accounts = []
    for ac in unth:
        accounts.append(get_context_user(ac.user))
    for ac in auth:
        accounts.append(get_context_user(ac.user))
    cont['accounts'] = accounts

    perms = get_ordered_perms()
    pdic = []
    for p in perms:
            pdic.append(p.name)
    cont['all_perms'] = pdic

    cont['filter_type'] = 'all'
    cont['filter_dept'] = None

    cont['user'] = get_context_user(request.user)

    return render_to_response('allaccounts.html',cont,
                       context_instance=RequestContext(request))

