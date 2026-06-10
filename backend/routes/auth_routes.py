from flask import Blueprint, request, jsonify
from backend.models.auth import User, UserSession, Role, Permission, CompanyUserMapping
from backend.models.company import Company
from datetime import datetime
import secrets
from bson import ObjectId

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    user = User.objects(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid credentials"}), 401
    
    if not user.is_active:
        return jsonify({"error": "Account deactivated by administrator"}), 403

    # Create session
    token = secrets.token_hex(32)
    session = UserSession(user=user, token=token)
    session.save()

    # Invalidate previous sessions if single login is enforced (optional)
    # UserSession.objects(user=user, token__ne=token, is_expired=False).update(is_expired=True, logout_time=datetime.utcnow())

    return jsonify({
        "token": token,
        "user": {
            "id": str(user.id),
            "username": user.username,
            "is_super_admin": user.is_super_admin
        }
    })

@auth_bp.route('/validate_session', methods=['POST'])
def validate_session():
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({"error": "Missing token"}), 401
    
    session = UserSession.objects(token=token, is_expired=False).first()
    if not session:
        return jsonify({"error": "Session invalid or expired"}), 401
    
    if not session.user.is_active:
        session.is_expired = True
        session.logout_time = datetime.utcnow()
        session.save()
        return jsonify({"error": "Account deactivated by administrator"}), 403

    session.touch()
    return jsonify({"status": "active", "is_super_admin": session.user.is_super_admin})

@auth_bp.route('/logout', methods=['POST'])
def logout():
    token = request.headers.get('Authorization')
    if token:
        UserSession.objects(token=token).update(is_expired=True, logout_time=datetime.utcnow())
    return jsonify({"status": "logged_out"})

@auth_bp.route('/my_companies', methods=['GET'])
def get_my_companies():
    token = request.headers.get('Authorization')
    session = UserSession.objects(token=token, is_expired=False).first()
    if not session:
        return jsonify({"error": "Unauthorized"}), 401
    
    user = session.user
    if user.is_super_admin:
        # Super admin sees everything
        companies = Company.objects.all()
        return jsonify([{
            "id": str(c.id),
            "name": c.name,
            "role": "Super Admin",
            "is_default": False
        } for c in companies])
    
    mappings = CompanyUserMapping.objects(user=user, is_active=True)
    results = []
    for m in mappings:
        company = Company.objects(id=m.company_id).first()
        if company:
            results.append({
                "id": str(company.id),
                "name": company.name,
                "role": m.role.name,
                "is_default": m.is_default_company
            })
    return jsonify(results)

@auth_bp.route('/permissions', methods=['GET'])
def get_permissions():
    token = request.headers.get('Authorization')
    company_id = request.args.get('company_id')
    session = UserSession.objects(token=token, is_expired=False).first()
    if not session:
        return jsonify({"error": "Unauthorized"}), 401
    
    if session.user.is_super_admin:
        return jsonify({"is_super_admin": True})

    if not company_id:
        return jsonify({"error": "Company ID required"}), 400
    
    mapping = CompanyUserMapping.objects(user=session.user, company_id=ObjectId(company_id), is_active=True).first()
    if not mapping:
        return jsonify({"error": "No access to this company"}), 403
    
    perms = Permission.objects(role=mapping.role)
    return jsonify({
        "role": mapping.role.name,
        "permissions": [{
            "module": p.module.lower().strip(),
            "can_view": p.can_view,
            "can_add": p.can_add,
            "can_edit": p.can_edit,
            "can_delete": p.can_delete,
            "can_print": p.can_print
        } for p in perms]
    })

# ── User Management (Super Admin only) ───────────────────────────────────────

def _is_admin():
    token = request.headers.get('Authorization')
    session = UserSession.objects(token=token, is_expired=False).first()
    return session and session.user.is_super_admin

@auth_bp.route('/users', methods=['GET'])
def list_users():
    if not _is_admin(): return jsonify({"error": "Admin only"}), 403
    users = User.objects.all()
    return jsonify([{
        "id": str(u.id),
        "username": u.username,
        "is_active": u.is_active,
        "is_super_admin": u.is_super_admin
    } for u in users])

@auth_bp.route('/users', methods=['POST'])
def create_user():
    if not _is_admin(): return jsonify({"error": "Admin only"}), 403
    data = request.json
    if User.objects(username=data['username']).first():
        return jsonify({"error": "User already exists"}), 400
    
    user = User(username=data['username'], is_super_admin=data.get('is_super_admin', False))
    user.set_password(data['password'])
    user.save()
    return jsonify({"status": "created", "id": str(user.id)})

@auth_bp.route('/roles', methods=['GET'])
def list_roles():
    if not _is_admin(): return jsonify({"error": "Admin only"}), 403
    roles = Role.objects.all()
    return jsonify([{"id": str(r.id), "name": r.name} for r in roles])

@auth_bp.route('/roles/<rid>/permissions', methods=['GET'])
def get_role_permissions(rid):
    if not _is_admin(): return jsonify({"error": "Admin only"}), 403
    role = Role.objects(id=ObjectId(rid)).first()
    if not role:
        return jsonify({"error": "Role not found"}), 404
    perms = Permission.objects(role=role)
    return jsonify({
        "role_id": str(role.id),
        "permissions": {
            p.module.lower().strip(): {
                "view": p.can_view,
                "edit": p.can_add,
                "delete": p.can_delete,
                "update": p.can_edit
            } for p in perms
        }
    })

@auth_bp.route('/roles/permissions', methods=['POST'])
def save_role_permissions():
    if not _is_admin(): return jsonify({"error": "Admin only"}), 403
    data = request.json or {}
    role_id = data.get('role_id')
    permissions_data = data.get('permissions', {})
    role = Role.objects(id=ObjectId(role_id)).first()
    if not role:
        return jsonify({"error": "Role not found"}), 404
    for module_name, actions in permissions_data.items():
        Permission.objects(role=role, module=module_name.lower().strip()).update_one(
            set__can_view=actions.get('view', False),
            set__can_add=actions.get('edit', False),
            set__can_edit=actions.get('update', False),
            set__can_delete=actions.get('delete', False),
            upsert=True
        )
    return jsonify({"status": "updated"})

@auth_bp.route('/companies/all', methods=['GET'])
def list_all_companies():
    if not _is_admin(): return jsonify({"error": "Admin only"}), 403
    companies = Company.objects.all()
    return jsonify([{"id": str(c.id), "name": c.name} for c in companies])

@auth_bp.route('/mappings', methods=['POST'])
def create_mapping():
    if not _is_admin(): return jsonify({"error": "Admin only"}), 403
    data = request.json
    user = User.objects(id=ObjectId(data['user_id'])).first()
    role = Role.objects(id=ObjectId(data['role_id'])).first()
    if not user or not role: return jsonify({"error": "Invalid user/role"}), 400
    
    mapping = CompanyUserMapping(
        user=user,
        company_id=ObjectId(data['company_id']),
        role=role,
        is_active=True
    )
    mapping.save()
    return jsonify({"status": "mapped"})
@auth_bp.route('/mappings', methods=['GET'])
def list_mappings():
    if not _is_admin(): return jsonify({"error": "Admin only"}), 403
    cid = request.args.get('company_id')
    uid = request.args.get('user_id')
    
    query = {}
    if cid: query['company_id'] = ObjectId(cid)
    if uid: query['user'] = ObjectId(uid)
    
    mappings = CompanyUserMapping.objects(**query)
    results = []
    for m in mappings:
        results.append({
            "id": str(m.id),
            "user_id": str(m.user.id),
            "username": m.user.username,
            "company_id": str(m.company_id),
            "role": m.role.name,
            "is_active": m.is_active
        })
    return jsonify(results)

@auth_bp.route('/mappings/<mid>', methods=['DELETE'])
def delete_mapping(mid):
    if not _is_admin(): return jsonify({"error": "Admin only"}), 403
    CompanyUserMapping.objects(id=ObjectId(mid)).delete()
    return jsonify({"status": "deleted"})

def check_permission_backend(module: str, action: str) -> bool:
    token = request.headers.get('Authorization')
    if not token:
        return False
    session = UserSession.objects(token=token, is_expired=False).first()
    if not session or not session.user:
        return False
    if session.user.is_super_admin:
        return True
    
    # Extract company_id from request args, body, or headers
    company_id = request.headers.get('X-Company-Id') or request.args.get('company_id')
    if not company_id and request.json:
        company_id = request.json.get('company_id')
        
    if not company_id:
        # Fallback to any active mapping for this user
        mapping = CompanyUserMapping.objects(user=session.user, is_active=True).first()
    else:
        try:
            mapping = CompanyUserMapping.objects(user=session.user, company_id=ObjectId(company_id), is_active=True).first()
        except:
            mapping = None
            
    if not mapping:
        return False
        
    p = Permission.objects(role=mapping.role, module=module.lower().strip()).first()
    if not p:
        return False
        
    if action == 'view': return p.can_view
    if action == 'edit': return p.can_add
    if action == 'update': return p.can_edit
    if action == 'delete': return p.can_delete
    return False
