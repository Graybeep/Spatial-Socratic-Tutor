CLAUDE.md §9.5 - diagnosis read-through
Call 1: openai/gpt-oss-120b via groq

Read the diagnosis against the three lines above it. The question is
not 'is it well written' but 'does it describe THIS student'.

---  1 ----------------------------------------------------------
  item      itm_0001 (node_click) on 'Packet Flow', turn 1
  SAW       52 nodes lit when the student chose
  TRUTH     student knows: zero         clicked 'reservation_based' -> wrong
  tutor     correct=False  state=guessing  action=hint_visual  (then hint 1)
  focus     ['flow', 'best_effort', 'reservation_based', 'congestion_control']
  DIAGNOSIS Student clicked Reservation-Based, which is unrelated to the target Packet Flow, indicating a random guess rather than a focused prerequisite error.

---  2 ----------------------------------------------------------
  item      itm_0001 (node_click) on 'Packet Flow', turn 2
  SAW       12 nodes lit when the student chose
  TRUTH     student knows: zero         clicked 'bottleneck_router' -> wrong
  tutor     correct=False  state=guessing  action=hint_visual  (then hint 2)
  focus     ['flow', 'best_effort', 'resource_allocation', 'flow_control']
  DIAGNOSIS Clicks on Reservation-Based and Bottleneck Router show no clear upstream focus; they are unrelated to the target, indicating the student is guessing.

---  3 ----------------------------------------------------------
  item      itm_0001 (node_click) on 'Packet Flow', turn 3
  SAW       9 nodes lit when the student chose
  TRUTH     student knows: zero         clicked 'soft_state' -> wrong
  tutor     correct=False  state=guessing  action=hint_visual  (then hint 3)
  focus     ['flow', 'best_effort', 'reservation_based', 'resource_allocation']
  DIAGNOSIS Student clicks are scattered across unrelated concepts (Reservation-Based, Bottleneck Router, Soft State) with no convergence toward the target flow, indicating guessing behavior.

---  4 ----------------------------------------------------------
  item      itm_0006 (node_click) on 'Best-Effort Service', turn 1
  SAW       52 nodes lit when the student chose
  TRUTH     student knows: partial      clicked 'best_effort' -> RIGHT
  tutor     correct=True  state=correct  action=advance  (then hint 0)
  focus     []
  DIAGNOSIS Student selected Best-Effort Service, which matches the answer, showing they identified the concept correctly despite the prior resource allocation prompt.

---  5 ----------------------------------------------------------
  item      itm_0001 (node_click) on 'Packet Flow', turn 2
  SAW       52 nodes lit when the student chose
  TRUTH     student knows: partial      clicked 'flow' -> RIGHT
  tutor     correct=True  state=correct  action=advance  (then hint 0)
  focus     []
  DIAGNOSIS Student correctly identified the Packet Flow node for the definition.

---  6 ----------------------------------------------------------
  item      itm_0041 (node_click) on 'Queuing Delay', turn 3
  SAW       52 nodes lit when the student chose
  TRUTH     student knows: partial      clicked 'power_metric' -> wrong
  tutor     correct=False  state=guessing  action=hint_visual  (then hint 1)
  focus     ['queuing_delay', 'fifo', 'tail_drop', 'fair_queuing', 'weighted_fair_queuing', 'avg_queue_length']
  DIAGNOSIS Student clicks are on unrelated concepts (Best-Effort Service, Packet Flow, Power) with no clear pattern toward Queuing Delay, indicating random guessing.

---  7 ----------------------------------------------------------
  item      itm_0011 (node_click) on 'Bottleneck Router', turn 1
  SAW       52 nodes lit when the student chose
  TRUTH     student knows: adversarial  clicked 'flow' -> wrong
  tutor     correct=False  state=on_track  action=hint_visual  (then hint 1)
  focus     ['bottleneck_router', 'congestion_control', 'queuing_delay', 'router_centric']
  DIAGNOSIS Student answered the prerequisite question about Packet Flow correctly, indicating they grasp basic flow ideas but have not yet attempted the bottleneck router identification.

---  8 ----------------------------------------------------------
  item      itm_0011 (node_click) on 'Bottleneck Router', turn 2
  SAW       12 nodes lit when the student chose
  TRUTH     student knows: adversarial  clicked 'flow' -> wrong
  tutor     correct=False  state=confused_prereq  action=hint_visual  (then hint 0)
  focus     ['bottleneck_router', 'congestion_control', 'queuing_delay', 'router_centric']
  DIAGNOSIS Student keeps clicking Packet Flow, suggesting they haven't grasped the Congestion Control prerequisite needed to identify Bottleneck Router.

---  9 ----------------------------------------------------------
  item      itm_0001 (node_click) on 'Packet Flow', turn 3
  SAW       52 nodes lit when the student chose
  TRUTH     student knows: adversarial  clicked 'flow' -> RIGHT
  tutor     correct=True  state=correct  action=advance  (then hint 0)
  focus     []
  DIAGNOSIS Student clicked the Packet Flow node, which matches the answer 'flow', indicating they identified the correct concept.

--- 10 ----------------------------------------------------------
  item      itm_0016 (node_click) on 'Soft State', turn 1
  SAW       52 nodes lit when the student chose
  TRUTH     student knows: zero         clicked 'dctcp' -> wrong
  tutor     correct=False  state=guessing  action=hint_visual  (then hint 1)
  focus     ['soft_state', 'resource_allocation']
  DIAGNOSIS Student clicked DCTCP, a node in the congestion control region unrelated to the target Soft State, indicating a lack of focus on relevant concepts.

--- 11 ----------------------------------------------------------
  item      itm_0016 (node_click) on 'Soft State', turn 2
  SAW       12 nodes lit when the student chose
  TRUTH     student knows: zero         clicked 'vegas_expected_rate' -> wrong
  tutor     correct=False  state=guessing  action=hint_visual  (then hint 0)
  focus     ['soft_state', 'resource_allocation', 'router_centric', 'best_effort', 'flow']
  DIAGNOSIS Student clicked DCTCP and Expected Rate, both in the congestion control region, showing no movement toward Soft State or its prerequisites.

--- 12 ----------------------------------------------------------
  item      itm_0001 (node_click) on 'Packet Flow', turn 3
  SAW       52 nodes lit when the student chose
  TRUTH     student knows: zero         clicked 'priority_queuing' -> wrong
  tutor     correct=False  state=guessing  action=hint_visual  (then hint 1)
  focus     ['flow', 'best_effort', 'flow_control', 'throughput']
  DIAGNOSIS Student clicks are scattered across unrelated concepts (DCTCP, Expected Rate, Priority Queuing) showing no clustering around the target or its prerequisites, indicating guessing.

--- 13 ----------------------------------------------------------
  item      itm_0021 (node_click) on 'Resource Allocation', turn 1
  SAW       52 nodes lit when the student chose
  TRUTH     student knows: partial      clicked 'flow' -> wrong
  tutor     correct=False  state=on_track  action=hint_visual  (then hint 1)
  focus     ['resource_allocation', 'best_effort', 'reservation_based', 'feedback_based', 'explicit_feedback']
  DIAGNOSIS Student previously clicked Packet Flow on a different prompt, showing they are still exploring the map; for the current Resource Allocation question there is no evidence of prerequisite confusion yet.

--- 14 ----------------------------------------------------------
  item      itm_0021 (node_click) on 'Resource Allocation', turn 2
  SAW       12 nodes lit when the student chose
  TRUTH     student knows: partial      clicked 'best_effort' -> wrong
  tutor     correct=False  state=on_track  action=hint_visual  (then hint 0)
  focus     ['resource_allocation', 'best_effort', 'reservation_based', 'feedback_based', 'explicit_feedback', 'implicit_feedback']
  DIAGNOSIS Student is exploring related concepts like Packet Flow and Best-Effort Service, indicating they understand the general area but have not pinpointed Resource Allocation yet.

--- 15 ----------------------------------------------------------
  item      itm_0001 (node_click) on 'Packet Flow', turn 3
  SAW       52 nodes lit when the student chose
  TRUTH     student knows: partial      clicked 'bottleneck_router' -> wrong
  tutor     correct=False  state=guessing  action=hint_visual  (then hint 1)
  focus     ['flow', 'throughput', 'congestion_control', 'resource_allocation']
  DIAGNOSIS After initially clicking the correct node, the student clicked unrelated concepts (Best-Effort Service, Bottleneck Router), showing a scattered pattern rather than following prerequisite links, which indicates guessing.

--- 16 ----------------------------------------------------------
  item      itm_0026 (node_click) on 'Congestion Control', turn 1
  SAW       52 nodes lit when the student chose
  TRUTH     student knows: adversarial  clicked 'resource_allocation' -> wrong
  tutor     correct=False  state=confused_prereq  action=hint_visual  (then hint 1)
  focus     ['congestion_control', 'feedback_based', 'explicit_feedback', 'window_based', 'rate_based']
  DIAGNOSIS Student clicked Resource Allocation, indicating they associate congestion control with resource allocation but have not identified the specific congestion_control concept.

--- 17 ----------------------------------------------------------
  item      itm_0026 (node_click) on 'Congestion Control', turn 2
  SAW       12 nodes lit when the student chose
  TRUTH     student knows: adversarial  clicked 'resource_allocation' -> wrong
  tutor     correct=False  state=confused_prereq  action=hint_visual  (then hint 0)
  focus     ['congestion_control', 'resource_allocation', 'feedback_based', 'explicit_feedback', 'window_based']
  DIAGNOSIS Student keeps clicking Resource Allocation, indicating they are stuck on the prerequisite and have not identified the higher-level Congestion Control concept required by the definition.

--- 18 ----------------------------------------------------------
  item      itm_0021 (node_click) on 'Resource Allocation', turn 3
  SAW       52 nodes lit when the student chose
  TRUTH     student knows: adversarial  clicked 'best_effort' -> wrong
  tutor     correct=False  state=confused_prereq  action=backtrack  (then hint 1)
  focus     ['best_effort']
  DIAGNOSIS Student clicked Best-Effort Service after being prompted to review foundations, suggesting they lack the prerequisite understanding needed for Resource Allocation.

--- 19 ----------------------------------------------------------
  item      itm_0031 (node_click) on 'Flow Control', turn 1
  SAW       52 nodes lit when the student chose
  TRUTH     student knows: zero         clicked 'finish_time' -> wrong
  tutor     correct=False  state=guessing  action=hint_visual  (then hint 1)
  focus     ['flow_control', 'window_based', 'rate_based', 'feedback_based', 'explicit_feedback', 'implicit_feedback']
  DIAGNOSIS Student clicked Finish Time, a concept unrelated to Flow Control, showing a scattered guess rather than targeting upstream prerequisites.

--- 20 ----------------------------------------------------------
  item      itm_0031 (node_click) on 'Flow Control', turn 2
  SAW       12 nodes lit when the student chose
  TRUTH     student knows: zero         clicked 'loss_as_signal' -> wrong
  tutor     correct=False  state=guessing  action=hint_visual  (then hint 0)
  focus     ['flow_control', 'feedback_based', 'explicit_feedback', 'implicit_feedback', 'window_based']
  DIAGNOSIS Student clicked Finish Time and Loss as a Congestion Signal, both in the congestion control cluster, showing no convergence toward the Flow Control node.

--- 21 ----------------------------------------------------------
  item      itm_0026 (node_click) on 'Congestion Control', turn 3
  SAW       52 nodes lit when the student chose
  TRUTH     student knows: zero         clicked 'fast_recovery' -> wrong
  tutor     correct=False  state=guessing  action=hint_visual  (then hint 1)
  focus     ['congestion_control', 'feedback_based', 'window_based', 'rate_based']
  DIAGNOSIS Student is selecting specific mechanisms (Finish Time, Loss as a Congestion Signal, Fast Recovery) under Congestion Control, indicating they are guessing among related concepts rather than identifying the high‑level definition.

--- 22 ----------------------------------------------------------
  item      itm_0036 (node_click) on 'Throughput', turn 1
  SAW       52 nodes lit when the student chose
  TRUTH     student knows: partial      clicked 'throughput' -> RIGHT
  tutor     correct=True  state=correct  action=advance  (then hint 0)
  focus     []
  DIAGNOSIS Student correctly identified the Throughput concept on the first attempt.

--- 23 ----------------------------------------------------------
  item      itm_0001 (node_click) on 'Packet Flow', turn 2
  SAW       52 nodes lit when the student chose
  TRUTH     student knows: partial      clicked 'bottleneck_router' -> wrong
  tutor     correct=False  state=guessing  action=hint_visual  (then hint 1)
  focus     ['flow', 'best_effort', 'resource_allocation', 'throughput']
  DIAGNOSIS Student is clicking downstream concepts such as Throughput and Bottleneck Router, showing no clear pattern toward prerequisites of the target; behavior looks like guessing.

--- 24 ----------------------------------------------------------
  item      itm_0001 (node_click) on 'Packet Flow', turn 3
  SAW       12 nodes lit when the student chose
  TRUTH     student knows: partial      clicked 'flow' -> RIGHT
  tutor     correct=True  state=correct  action=advance  (then hint 0)
  focus     []
  DIAGNOSIS Student clicked the Packet Flow node, matching the definition provided.

--- 25 ----------------------------------------------------------
  item      itm_0041 (node_click) on 'Queuing Delay', turn 1
  SAW       52 nodes lit when the student chose
  TRUTH     student knows: adversarial  clicked 'queuing_delay' -> RIGHT
  tutor     correct=True  state=correct  action=advance  (then hint 0)
  focus     []
  DIAGNOSIS Student clicked the Queuing Delay node, which matches the answer.

--- 26 ----------------------------------------------------------
  item      itm_0001 (node_click) on 'Packet Flow', turn 2
  SAW       52 nodes lit when the student chose
  TRUTH     student knows: adversarial  clicked 'resource_allocation' -> wrong
  tutor     correct=False  state=guessing  action=hint_visual  (then hint 1)
  focus     ['flow', 'best_effort', 'reservation_based', 'feedback_based']
  DIAGNOSIS Student's clicks (Queuing Delay, Resource Allocation) lie in unrelated regions of the map and show no convergence toward the Packet Flow concept.

--- 27 ----------------------------------------------------------
  item      itm_0001 (node_click) on 'Packet Flow', turn 3
  SAW       12 nodes lit when the student chose
  TRUTH     student knows: adversarial  clicked 'bottleneck_router' -> wrong
  tutor     correct=False  state=guessing  action=hint_visual  (then hint 2)
  focus     ['flow', 'best_effort', 'congestion_control', 'throughput', 'resource_allocation']
  DIAGNOSIS Clicks are on Queuing Delay, Resource Allocation, and Bottleneck Router, which are in disparate parts of the map, showing no coherent prerequisite focus, suggesting the student is guessing.

--- 28 ----------------------------------------------------------
  item      itm_0046 (node_click) on 'Power', turn 1
  SAW       12 nodes lit when the student chose
  TRUTH     student knows: zero         clicked 'rate_based' -> wrong
  tutor     correct=False  state=guessing  action=hint_visual  (then hint 2)
  focus     ['throughput', 'queuing_delay', 'resource_allocation', 'power_metric']
  DIAGNOSIS Student clicked Rate-Based Control, which is unrelated to the Power Metric concept, showing a lack of direction and suggesting random guessing.

--- 29 ----------------------------------------------------------
  item      itm_0046 (node_click) on 'Power', turn 2
  SAW       9 nodes lit when the student chose
  TRUTH     student knows: zero         clicked 'vegas_expected_rate' -> wrong
  tutor     correct=False  state=guessing  action=hint_visual  (then hint 0)
  focus     ['throughput', 'queuing_delay', 'power_metric']
  DIAGNOSIS Student selected Rate-Based Control and Expected Rate, which lie in the congestion-control side of the map rather than near the throughput or delay concepts that underpin Power, indicating they are guessing.

--- 30 ----------------------------------------------------------
  item      itm_0041 (node_click) on 'Queuing Delay', turn 3
  SAW       52 nodes lit when the student chose
  TRUTH     student knows: zero         clicked 'decbit' -> wrong
  tutor     correct=False  state=guessing  action=hint_visual  (then hint 1)
  focus     ['queuing_delay', 'fifo', 'tail_drop', 'priority_queuing', 'fair_queuing', 'weighted_fair_queuing', 'avg_queue_length']
  DIAGNOSIS Student's clicks (Rate-Based Control, Expected Rate, DECbit) are in unrelated branches of the map, showing no pattern toward Queuing Delay.


==============================================================
WHAT IS CHECKABLE WITHOUT A HUMAN (this is not §9.5, it bounds it)
==============================================================

Call 1 (wrote every diagnosis below): openai/gpt-oss-120b via groq

`correct` vs what the student actually clicked: 30/30 = 100%

student_state against the student's TRUE knowledge state:

    true \ said      confused_prereq           correct          guessing          on_track
    adversarial                    4                 2                 2                 1
    partial                        0                 4                 3                 2
    zero                           0                 0                12                 0

actions requested: {'hint_visual': 23, 'advance': 6, 'backtrack': 1}
