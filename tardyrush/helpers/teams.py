from consts import StatsGrouperDefault, StatsGrouperStringMapping

def grouper_id_to_int(gid):
    return StatsGrouperStringMapping.get(gid, StatsGrouperDefault)
