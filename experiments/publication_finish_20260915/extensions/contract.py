"""A matched retreat-only control; do not alter frozen main-run modules on disk."""
import sys

ARMS = ('continue_h8', 'physical_regrasp', 'retreat_requery')
PRIMARY = (('replication', 'physical_regrasp', 'retreat_requery'),
           ('transfer', 'physical_regrasp', 'retreat_requery'),
           ('all', 'retreat_requery', 'continue_h8'))


def install():
    import recovery_confirmation as protocol
    protocol.ARMS = ARMS
    protocol.PRIMARY = PRIMARY
    sys.modules['scripts.recovery_confirmation'] = protocol
    return protocol


def install_intervention():
    import observation_contract as oc
    original = oc.intervene

    def intervene(c, p, r, env, obs, tracker, localizer, artifact, description,
                  cfg, arm, loc, t, job, model, stats, resize):
        if arm != 'retreat_requery':
            return original(c,p,r,env,obs,tracker,localizer,artifact,description,
                            cfg,arm,loc,t,job,model,stats,resize)
        decision = oc.gate(loc, r._eef_position(obs), artifact)
        diag = dict(initial_trigger_passed=decision.passed, initial_gate=decision.__dict__,
                    repair_requested=False, refresh_requested=decision.passed,
                    control='same_initial_gate_then_open_retreat_relocalize_no_grasp',
                    probe_steps=0, regrasp_steps=0, oracle=False)
        success = bool(env.check_success())
        if decision.passed and not success:
            obs, success, t, n, info = oc.primitive(c,p,r,env,obs,tracker,localizer,
                artifact,description,cfg,t,gripper=-1.,observe_only=True,
                locate=lambda current:p._localize(env,current,localizer,description))
            diag.update(probe_steps=n, regrasp_diagnostics=info)
        return obs, success, t, diag, [], 5
    oc.intervene = intervene
