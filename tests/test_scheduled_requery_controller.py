from cosmos_policy.experiments.robot.libero.scheduled_requery import (
    scheduled_requery_decision,
)


def test_scheduled_requery_executes_two_short_chunks_at_query_boundary() -> None:
    steps = []
    triggers = []
    active = []
    completions = []
    for query_idx in range(7):
        decision = scheduled_requery_decision(
            query_idx=query_idx,
            scheduled_query_idx=4,
            open_loop_steps=16,
            short_open_loop_steps=8,
        )
        selected_steps, trigger, is_active, completion = decision
        steps.append(selected_steps)
        triggers.append(trigger)
        active.append(is_active)
        completions.append(completion)

    assert steps == [16, 16, 16, 16, 8, 8, 16]
    assert triggers == [False, False, False, False, True, False, False]
    assert active == [False, False, False, False, True, True, False]
    assert completions == [False, False, False, False, False, True, False]
