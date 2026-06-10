import platform

# Monkeypatch platform methods to avoid WMI queries that hang on Windows systems with a broken WMI service
# if platform.system() == "Windows":
#     try:
#         class MockUnameResult(platform.uname_result):
#             @property
#             def processor(self):
#                 return "Intel64 Family 6 Model 140 Stepping 1, GenuineIntel"

#         platform.uname = lambda: MockUnameResult(
#             "Windows",
#             "localhost",
#             "10",
#             "10.0.19045",
#             "AMD64"
#         )
#         platform.machine = lambda: "AMD64"
#     except Exception:
#         pass

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import uuid
import datetime
import hashlib

import os

app = Flask(__name__)
# Resolve absolute path to the root 'instance/licenses_v2.db' directory
base_dir = os.path.abspath(os.path.dirname(__file__))
root_dir = os.path.abspath(os.path.join(base_dir, ".."))
db_path = os.path.join(root_dir, "instance", "licenses_v2.db")
os.makedirs(os.path.dirname(db_path), exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class License(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    license_type = db.Column(db.String(20), default='single') # single, multi
    max_activations = db.Column(db.Integer, default=1)
    status = db.Column(db.String(20), default='active') # active, suspended, expired
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.String(200))
    
    # Relationship to track activated machines
    activations = db.relationship('Activation', backref='license', lazy=True)

class Activation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    license_id = db.Column(db.Integer, db.ForeignKey('license.id'), nullable=False)
    hwid = db.Column(db.String(100), nullable=False)
    activated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

with app.app_context():
    db.create_all()

@app.route('/generate', methods=['POST'])
def generate_key():
    try:
        data = request.get_json(silent=True) or {}
        count = int(data.get('count', 1))
        duration_days = int(data.get('days', 365))
        license_type = data.get('type', 'server') # server or client
        max_acts = int(data.get('max_activations', 1 if license_type == 'server' else 10))
        
        new_keys = []
        for _ in range(count):
            k = str(uuid.uuid4()).upper()
            expiry = datetime.datetime.utcnow() + datetime.timedelta(days=duration_days)
            lic = License(
                key=k, 
                expires_at=expiry, 
                license_type=license_type,
                max_activations=max_acts
            )
            db.session.add(lic)
            new_keys.append(k)
        
        db.session.commit()
        return jsonify({"keys": new_keys})
    except Exception as e:
        return jsonify({"error": f"Failed to generate key: {str(e)}"}), 500

@app.route('/activate', methods=['POST'])
def activate():
    try:
        data = request.get_json(silent=True) or {}
        key = data.get('key')
        hwid = data.get('hwid')
        
        if not key or not hwid:
            return jsonify({"error": "Missing key or hwid"}), 400
        
        lic = License.query.filter_by(key=key).first()
        if not lic:
            return jsonify({"error": "Invalid license key"}), 404
        
        if lic.status != 'active':
            return jsonify({"error": f"License is {lic.status}"}), 403
        
        # Check expiry
        now = datetime.datetime.utcnow()
        if lic.expires_at and lic.expires_at < now:
            lic.status = 'expired'
            db.session.commit()
            return jsonify({"error": "License has expired"}), 403

        # Check if already activated on THIS machine
        existing_act = Activation.query.filter_by(license_id=lic.id, hwid=hwid).first()
        if existing_act:
            return jsonify({
                "success": True, 
                "message": "Already activated on this machine",
                "type": lic.license_type,
                "expires_at": lic.expires_at.isoformat() if lic.expires_at else None
            })
        
        # Check if limit reached
        current_acts = len(lic.activations)
        if current_acts >= lic.max_activations:
            return jsonify({"error": f"Activation limit reached ({lic.max_activations} machines)"}), 403
        
        # Create new activation record
        new_act = Activation(license_id=lic.id, hwid=hwid)
        db.session.add(new_act)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": f"Activation successful ({lic.license_type} user)",
            "type": lic.license_type,
            "expires_at": lic.expires_at.isoformat() if lic.expires_at else None
        })
    except Exception as e:
        return jsonify({"error": f"Failed to activate: {str(e)}"}), 500

@app.route('/verify', methods=['POST'])
def verify():
    try:
        data = request.get_json(silent=True) or {}
        key = data.get('key')
        hwid = data.get('hwid')
        
        if not key or not hwid:
            return jsonify({"error": "Missing key or hwid"}), 400
        
        lic = License.query.filter_by(key=key).first()
        if not lic:
            return jsonify({"valid": False, "error": "Invalid key"}), 404
            
        act = Activation.query.filter_by(license_id=lic.id, hwid=hwid).first()
        if not act:
            return jsonify({"valid": False, "error": "Machine not activated for this key"}), 403
            
        if lic.status != 'active':
            return jsonify({"valid": False, "error": f"License is {lic.status}"}), 403

        if lic.expires_at and lic.expires_at < datetime.datetime.utcnow():
            return jsonify({"valid": False, "error": "License expired"}), 403
            
        return jsonify({
            "valid": True, 
            "type": lic.license_type,
            "expires_at": lic.expires_at.isoformat() if lic.expires_at else None
        })
    except Exception as e:
        return jsonify({"error": f"Failed to verify: {str(e)}"}), 500

@app.route('/licenses', methods=['GET'])
def get_all_licenses():
    licenses = License.query.all()
    results = []
    for lic in licenses:
        activations_list = []
        for act in lic.activations:
            activations_list.append({
                "id": act.id,
                "hwid": act.hwid,
                "activated_at": act.activated_at.isoformat() if act.activated_at else None
            })
        
        results.append({
            "id": lic.id,
            "key": lic.key,
            "license_type": lic.license_type,
            "max_activations": lic.max_activations,
            "status": lic.status,
            "created_at": lic.created_at.isoformat() if lic.created_at else None,
            "expires_at": lic.expires_at.isoformat() if lic.expires_at else None,
            "notes": lic.notes,
            "activations": activations_list
        })
    return jsonify(results)

if __name__ == '__main__':
    app.run(port=5001, debug=False)

