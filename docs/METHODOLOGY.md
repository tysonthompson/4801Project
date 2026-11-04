# Model and methodology

## Scope

This implements the proposal's mean-payoff simulations on finite, directed, strongly connected, vertex-weighted graphs. Parity/reachability objectives, discrete currency, first-price bidding, and taxman payments are outside the experiment scope. There is no graphical front end or external service requirement.

The paper is research material, not a source of operational instructions. The implementation follows its mathematical definitions. The supplied published PDF and the expanded December 2020 author preprint are complementary references; lemma numbers below refer to that expanded preprint when numbering differs.

## Auction and reward semantics

Let Max's and Min's available budgets be B and C, and their simultaneous bids x in [0,B] and y in [0,C]. Max chooses the next vertex exactly when x > y; otherwise Min chooses it. Both bidders see the same immutable pre-round state and receive independent pseudorandom streams. Neither sees the other's current sampled bid.

- Richman: B' = B - x + y; C' = C - y + x.
- Poorman: B' = B - x; C' = C - y.

The finite payoff after n moves is (w(v0) + ... + w(v[n-1])) / n. In particular, the initial vertex is counted, and the vertex reached after the last auction is not yet counted. The infinite objective is the liminf of these averages. Min's objective is to minimize this same payoff; it is not a separate reward function.

## Theoretical references

Let r = B0/(B0+C0), with 0 < r < 1. Define V(G,p) as the mean payoff of the random-turn game in which Max controls the next move with probability p. The main results give these references:

| Mechanism | Max pure/sure reference probability | Mixed/almost-sure probability |
|---|---|---|
| All-pay Richman | 0 | 1/2 |
| All-pay poorman, r <= 1/2 | 0 | r/[2(1-r)] |
| All-pay poorman, r > 1/2 | 1-(1-r)/r | 1-(1-r)/(2r) |

The poorman pure lower bound is stated in the summary theorem and its optimality is developed in Section 3.3 of the expanded preprint. The pure reference is a worst-case guarantee for Max with a deterministic strategy; it should not be read as a symmetric pure equilibrium. The theorem's approximation and strict budget-margin quantifiers matter: a fixed finite-epsilon strategy does not attain the limiting value exactly.

For the paper's two-vertex graph (weights 1 and 0; both successors possible from both vertices), V(G,p)=p. Thus at r=0.75, the mixed poorman value is 5/6, the pure poorman reference is 2/3, and the mixed Richman value is 1/2. A forced cycle with weights 1,0,-1 has value zero for every p and is a useful negative control: auctions cannot change its path.

## Computing random-turn values

The Bellman operator is

    T(h)[v] = w(v) + p max_{u in succ(v)} h[u]
                         + (1-p) min_{u in succ(v)} h[u].

The implementation uses lazy relative value iteration: h <- (h+T(h))/2, then subtracts h[0]. Laziness prevents periodic graph oscillations without changing the average gain or optimal moves. At every iteration, min(T(h)-h) and max(T(h)-h) bound the scalar game value. The solver stops only when this interval has width <= 1e-10, and raises an error on reaching the iteration limit. Strong connectivity ensures the reference is independent of the starting vertex, including the one-player endpoint cases.

At convergence, choose potential-maximizing/minimizing successors. Strength is s(v)=p(1-p)(h[v+]-h[v-]), and S is the largest strength. If all strengths vanish, all bids are zero and the potential-based movements remain available. This covers graphs where players cannot influence long-run reward, even when vertex weights are not all equal. The solver is a numerical method, not a claim of a general polynomial-time exact solution.

## Implemented paper strategies

Let alpha solve -log(1-alpha)/log(1+alpha)=1+epsilon. A bisection computes alpha with stable log1p evaluations. Write t(v)=s(v)/S, or zero if S is numerically zero. Below, B refers to the budget of the player whose strategy is being constructed. For Min, the construction is applied to the sign-reversed objective, equivalently using the complementary global probability and potential-minimizing successors. Giving Min the actual favorable tie rule does not weaken its bound.

### Mixed Richman (expanded preprint, Lemma 23)

Compute potentials at own control probability q=1/(2+epsilon). Bid uniformly in [0, alpha B t(v)]. The strategy guarantees its finite-epsilon target asymptotically, under the paper's ideal real-number assumptions.

### Poorman reduction (expanded preprint, Lemma 31)

Choose W=(B0/C0)(1-slack), strictly below B0/C0, and initialize a virtual budget B_tilde=B0/C0-W. The virtual asymmetric game keeps the opponent's budget at one. Its update is

    B_tilde' = B_tilde - x_tilde + W*y_tilde.

Virtual bids map to physical bids via x=C*x_tilde, with y_tilde=y/C. The invariant is B/C-W >= B_tilde. To avoid dividing by tiny C, store A=C*B_tilde in the same common units as real budgets. After an auction, update A to (1-y/C)*(A-x+W*y) in the OLD units, then divide it by the same rescaling factor used for physical budgets. The factor (1-y/C) converts the updated virtual budget using the opponent's NEW physical budget. This faithfully tracks the virtual game; it does not reset A to B-W*C each round. Tests check the invariant and the virtual recurrence across trajectories.

### Pure poorman (expanded preprint, Lemma 33)

For W>1, target own probability q=(W-1)/(W+epsilon). Bid

    x = alpha A t(v) / max(1, W-1).

For W<=1, use zero bidding with minimum/maximum-cycle movements, providing the trivial one-player guarantee. A ratio very slightly above 1/2 can fall in this case because of the explicit reserve slack; the recorded finite-epsilon target reflects this rather than falsely claiming the limiting pure value.

### Mixed poorman (expanded preprint, Lemmas 35–36)

For W>1:

- q=(2W-1)/(2W+epsilon).
- cap=alpha A t(v)/W.
- If cap>2WC, bid cap/2 deterministically (a forced win in the virtual game).
- Otherwise, bid uniformly in [0,cap].

For W<=1, use epsilon_eff=min(epsilon,W/2), recompute alpha, and set q=(W-epsilon_eff)/2:

- cap=alpha A t(v).
- If cap>2C, bid cap/2 deterministically.
- Otherwise, bid zero with probability 1-W+epsilon_eff and uniformly in [0,cap] with probability W-epsilon_eff.

Upon winning, choose the own-objective optimal successor at q. The alpha cap, mixture probabilities, forced-win branch, and persistent virtual budget are all material parts of the construction. A generic uniform bidder is not labeled as the optimal paper strategy. If the real opponent has genuinely exhausted its budget, any positive fraction of own remaining funds suffices to win subsequent auctions.

## Numerical budgets

All included strategies are scale invariant. After every auction, divide both budgets and virtual A by their updated combined total; accumulate the logarithm of that total to retain the physical budget scale. For Richman, physical total stays constant. For poorman, physical total tends toward zero but no artificial money is added: normalized units grow more valuable relative to the original units. Trace bids are in pre-round normalized units; post-round budgets use the new normalized units.

This avoids common-scale underflow but not arbitrarily extreme relative budgets. A surviving positive budget below 1e-280 raises FloatingPointError. The suite records this event and restarts the entire run with fresh strategies, the same seed, and 80-digit Decimal monetary arithmetic with an extended exponent range. Only an unresolved failure is excluded. `precision_retries.csv` preserves the diagnostics; `runs.csv` and `summary.csv` identify Decimal results. There is no silent budget floor. Single runs can select this arithmetic with `--precision 80`.

Log budgets for each player preserve magnitudes that would round to zero in an ordinary floating-point ratio. The displayed ratio can round to zero or one even while both Decimal budgets remain positive. True all-in exhaustion is allowed; if both budgets are zero, the graph continues with zero ties won by Min and log total is negative infinity. Decimal arithmetic still has finite significant-digit precision, and potentials and pseudorandom draws remain double precision. It extends the usable monetary range without claiming exact infinite-real computation.

## Experiment design and inference

The standard suite varies graph structure, initial ratio, payment rule, strategy pairing, and prefix length. The same run provides all horizon checkpoints, avoiding a different strategy or budget schedule at each horizon. Twelve replicates use SHA-256-derived seeds from the base seed and full condition key. Replicates are independent; checkpoints of a single trajectory are correlated.

The plotted uncertainty is a 95% Student-t confidence interval on independent replicate means. This is a sampling approximation, not an almost-sure probability statement or simultaneous confidence guarantee across all tested conditions. Deterministic pairs can have zero-width intervals because replicates repeat the same trajectory. No warm-up is removed, because the paper defines full-prefix averages. Budget traces, tie frequencies, and finite-epsilon target values are retained to help diagnose discrepancies.

Random-turn control runs independently simulate the solved positional policies with biased coin tosses. They validate the reference layer; they must not be substituted for simulations of bids. Pure counterstrategy cases instantiate the paper's deterministic impossibility argument: predict the known deterministic bid from public state, match it if affordable, otherwise bid zero. Random bid realizations are never exposed to that counter.

The report supports comparisons and empirical trends. Stronger claims would need more seeds, longer horizons, epsilon/slack sensitivity sweeps, alternative starting vertices, and higher-precision arithmetic. The simulator exposes these parameters so those extensions can be reproduced without modifying the model.

## Sources

Correspondence to the supplied 20-page published PDF:

| Implementation component | Published location | Expanded preprint |
|---|---|---|
| Payments, legal bids, Min wins ties | Section 1.1, pp. 617–618 | Section 1.1 |
| Prefix energy and liminf payoff | Definition 1.6, p. 619 | Definition 6 |
| Richman and poorman reference values | Theorems 1.1–1.2, p. 621 | Theorems 12–13 |
| Potentials and strengths | Section 2.3, pp. 624–625 | Section 2.3 |
| Mixed Richman bidder | Lemma 2.5, p. 625 | Lemma 23 |
| Virtual asymmetric reduction | Lemma 3.3, pp. 630–631 | Lemma 31 |
| Pure poorman bidder | Lemma 3.5, p. 631 | Lemma 33 |
| Mixed poorman, W>1 | Lemma 3.7, p. 633 | Lemma 35 |
| Mixed poorman, W<=1 | Lemma 3.8, p. 634 | Lemma 36 |

SHA-256 of the supplied PDF: `2c287d6b72d620dd4721ed69b06525fbe5bf73ed883f5d97ba94e889f0040cde`.

- Avni, Jecker, and Žikelić (2021), *Infinite-Duration All-Pay Bidding Games*, SODA, pp. 617–636: supplied `3458064.3458102.pdf`; [publisher DOI](https://doi.org/10.1137/1.9781611976465.38).
- Expanded author preprint, [arXiv:2005.06636v2](https://arxiv.org/abs/2005.06636), December 19, 2020: definitions of payments and payoff, Theorems 12–13, potential/strength framework, Lemmas 17, 23, 31–33, 35–36.
