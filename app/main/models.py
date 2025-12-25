from app import db


class Project(db.Model):
    __tablename__ = "projects"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), unique=True)
    married = db.Column(db.Boolean)
    nb_children = db.Column(db.Integer)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'married': self.married,
            'nb_children': self.nb_children
        }
