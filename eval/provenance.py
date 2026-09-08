"""Sampling provenance for every eval output.

WHY THIS MODULE EXISTS
----------------------
Twice now this project has shipped a number that was structurally wrong in a way
no assertion caught, because both times the assertions were about the SHAPE of a
value rather than about what produced it.

  ItemPublic.node_id   The leak tests compared STRINGS. The answer to a
                       node_click item IS its node id, so shipping node_id
                       handed over the answer in the clear - and every test
                       passed, because no string in the payload matched a
                       forbidden string. The bug was one of IDENTITY, and the
                       tests only knew about equality of text.

  9.1 sampled one item Every dialogue drew from an identical initial state, so
                       60 dialogues produced 360 probes over ONE item out of
                       101. All 179 tests passed, because a rate computed over
                       one item has exactly the same shape as a rate computed
                       over a hundred: a float in [0, 1], under the right key,
                       in a dict with the right arms.

The common failure is that an eval result carries its VALUE but not its
PROVENANCE, so nothing downstream can tell a number that generalises from a
number that does not. A test can only check what the output carries.

So: every eval result embeds what it sampled, and coverage becomes assertable.
The cost is one call per measurement and one assertion per test. Either bug
above would have been caught on day one by `distinct == population`.

WHAT TO ASSERT
--------------
Not every eval must reach full coverage - a deliberately subsampled run is
legitimate. What must never happen again is coverage collapsing SILENTLY. So
`Provenance.coverage` is always reported, `expect_full` marks the runs that
intend completeness, and tests assert on it.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable, Optional


@dataclass(frozen=True)
class Provenance:
    """What a number was computed from.

    population       size of the set the result is generalised TO
    distinct         how many distinct members were actually sampled
    observations     total draws (>= distinct when members repeat)
    unit             what one member IS - the resampling unit for any CI
    expect_full      whether this run intends to cover the population
    """

    population: int
    distinct: int
    observations: int
    unit: str
    expect_full: bool = True

    @property
    def coverage(self) -> float:
        return (self.distinct / self.population) if self.population else 0.0

    @property
    def complete(self) -> bool:
        return self.population > 0 and self.distinct == self.population

    @property
    def degenerate(self) -> bool:
        """One distinct member, many observations: the signature of both bugs
        above. A confidence interval over this is undefined however large the
        observation count looks."""
        return self.distinct <= 1 and self.observations > 1

    def problem(self) -> Optional[str]:
        """Human-readable complaint, or None if the sampling is sound."""
        if self.population == 0:
            return f"population of {self.unit} is empty - nothing was sampled"
        if self.degenerate:
            return (f"{self.observations} observations over {self.distinct} distinct "
                    f"{self.unit} - this number describes one {self.unit[:-1] if self.unit.endswith('s') else self.unit}, "
                    f"not the {self.population} it is reported against")
        if self.expect_full and not self.complete:
            return (f"coverage {self.coverage:.0%}: {self.distinct} of "
                    f"{self.population} {self.unit} sampled, but this run "
                    f"intends full coverage")
        return None

    def as_dict(self) -> dict:
        d = asdict(self)
        d["coverage"] = round(self.coverage, 4)
        d["complete"] = self.complete
        return d


def over(population: Iterable, sampled: Iterable, observations: int,
         unit: str = "items", expect_full: bool = True) -> Provenance:
    """Build a Provenance from the population and what was actually drawn."""
    pop = set(population)
    drawn = set(sampled)
    return Provenance(
        population=len(pop),
        distinct=len(drawn & pop) if pop else len(drawn),
        observations=observations,
        unit=unit,
        expect_full=expect_full,
    )


def check(prov: Provenance) -> None:
    """Raise if the sampling cannot support a generalisation. Call this in
    tests, not in the measurement path - a run that samples badly should still
    produce its (labelled) number so the problem is visible rather than fatal."""
    problem = prov.problem()
    if problem:
        raise AssertionError(f"eval sampling is not sound: {problem}")
