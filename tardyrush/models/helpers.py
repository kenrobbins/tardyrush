from tardyrush import db

id_type = db.Integer(unsigned=True)
def create_id_column(name):
    return db.Column(name + '_id', id_type, primary_key=True, \
            autoincrement=True, nullable=False)

def create_name_column(name,unique=True):
    return db.Column(name+'_name', db.String(255), nullable=False,
            unique=unique)
