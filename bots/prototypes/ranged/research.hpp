#pragma once
// Scope: public probe for research timing, not a ladder submission.
#include "strategy.hpp"

namespace research {
enum class Policy { Melee, Fixed, Adaptive };

class RangedPolicy {
    const hrw::Setup& setup;
    hrw::Pos home, enemy;
    bool flipped;
    int last_deposit = 0, income16 = 0;
    bool unlocked = false;
    int cost(const char* name) const { return setup.params.at(name); }

    bool path_open(hrw::Pos from, hrw::Pos to) const {
        int dist = hrw::distance(from,to);
        if (dist != 2) return dist == 1;
        for (const auto& [direction,p] : hrw::neighbors(from)) {
            auto [x,y] = p;
            if (y >= 0 && y < int(setup.rows.size()) && x >= 0 && x < int(setup.rows[y].size())
                && setup.rows[y][x] == '.' && hrw::distance(p,to) == 1) return true;
        }
        return false;
    }

    int build_spend(const std::vector<std::string>& orders) const {
        return int(std::count_if(orders.begin(),orders.end(),[](const auto& s){return s.starts_with("BUILD ");}))
            * cost("TOWER_COST");
    }

    void shoot(const hrw::Turn& turn, std::vector<std::string>& orders, const std::vector<const hrw::Unit*>& ranged) const {
        struct Target { hrw::Pos pos; int hp, priority; };
        std::vector<Target> targets;
        std::set<int> range_ids;
        std::map<int,int> melee_damage;
        std::map<int,size_t> order_slots;
        std::map<hrw::Pos,int> assigned;
        for (auto u : ranged) range_ids.insert(u->id);
        for (const auto& u : turn.units) {
            if (u.owner != setup.you) targets.push_back({u.pos(),u.hp,1});
            else if (u.kind != "R") melee_damage[u.id] = cost(u.kind=="W"?"WORKER_DMG":"SOLDIER_DMG");
        }
        for (const auto& [x,y,owner,hp] : turn.towers)
            if (owner != setup.you) targets.push_back({{x,y},hp,2});
        targets.push_back({enemy,turn.players.at(1-setup.you)[2],0});
        for (size_t i=0; i<orders.size(); ++i) {
            std::istringstream line(orders[i]);
            std::string op; line>>op;
            if (op!="MOVE" && op!="ATTACK") continue;
            int id; line>>id;
            if (range_ids.contains(id)) order_slots[id]=i;
            else if (op=="ATTACK" && melee_damage.contains(id)) {
                int x,y; line>>x>>y;
                assigned[{x,y}] += melee_damage.at(id);
            }
        }
        for (auto unit : ranged) {
            const Target* best = nullptr;
            auto rank = [&](const Target& target) {
                auto [x,y] = target.pos;
                int hp = target.hp-assigned[target.pos];
                return std::tuple(hp<=0, hp>cost("RANGED_DMG"), target.priority, hp,
                    hrw::distance(unit->pos(),target.pos), flipped ? -y : y, flipped ? -x : x);
            };
            for (const auto& target : targets) if (path_open(unit->pos(),target.pos)
                && (!best || rank(target)<rank(*best))) best=&target;
            if (!best) continue;  // Keep the original movement when no shot is available.
            auto [x,y] = best->pos;
            std::string command = "ATTACK " + std::to_string(unit->id) + " " + std::to_string(x) + " " + std::to_string(y);
            auto it=order_slots.find(unit->id);
            if (it==order_slots.end()) orders.push_back(std::move(command));
            else orders[it->second]=std::move(command);
            assigned[best->pos]+=cost("RANGED_DMG");
        }
    }

public:
    explicit RangedPolicy(const hrw::Setup& s):setup(s),home(s.bases().at(s.you)),enemy(s.bases().at(1-s.you)),
        flipped(std::pair(home.second,home.first)>std::pair(enemy.second,enemy.first)) {}

    void apply(const hrw::Turn& turn, std::vector<std::string>& orders, Policy policy, int start, int reserve) {
        if (policy==Policy::Melee || !setup.params.contains("RANGED_UNLOCK_COST")) return;
        const auto& player=turn.players.at(setup.you);
        income16=(15*income16+16*(player[3]-last_deposit))/16;
        last_deposit=player[3];
        const std::string unlocked_event=" UNLOCKED "+std::to_string(setup.you)+" R";
        for (const auto& event : turn.events) if (event==unlocked_event) unlocked=true;
        int soldiers=0, workers=0, attackers=0, enemy_towers=0, opponents_within_turns=0;
        std::vector<const hrw::Unit*> ranged;
        for (const auto& unit : turn.units) {
            if (unit.owner==setup.you) {
                if (unit.kind=="W") ++workers;
                else ++soldiers;
                if (unit.kind=="R") ranged.push_back(&unit);
            } else if (unit.kind!="W") {
                int distance=hrw::distance(home,unit.pos());
                attackers += distance <= 10;
                opponents_within_turns += distance <= 18;
            }
        }
        for (const auto& [x,y,owner,hp] : turn.towers) enemy_towers += owner!=setup.you;
        const int soldier_cost=cost("SOLDIER_COST");
        const int budget=player[0]-build_spend(orders);
        auto production=std::find_if(orders.begin(),orders.end(),[](const auto& s){return s.starts_with("SPAWN ");});
        if (!unlocked) {
            bool ready = turn.number>=start && budget>=cost("RANGED_UNLOCK_COST")+reserve;
            if (policy==Policy::Adaptive) {
                const int remaining=cost("TURNS")-turn.number;
                const int defense=std::max(0,attackers+2-soldiers)*soldier_cost;
                // A cash surplus with a viable economy buys range; a local
                // surge or a nearly over game pays for soldiers instead.
                const bool meaningful = enemy_towers>=2 || opponents_within_turns>=2 || turn.number>=75;
                const bool sustainable = income16>=14*16 || budget>=6*soldier_cost;
                ready=turn.number>=28 && remaining>=75 && meaningful && sustainable && workers>=5
                    && budget>=cost("RANGED_UNLOCK_COST")+cost("RANGED_COST")+defense+soldier_cost
                    && (attackers==0 || soldiers>=attackers+2);
            }
            if (ready) {
                if (production==orders.end()) orders.push_back("UNLOCK R");
                else *production="UNLOCK R";
            }
            return;
        }
        if (production!=orders.end() && production->starts_with("SPAWN S ") && budget>=cost("RANGED_COST")
            && 3*int(ranged.size()) < soldiers+1) {
            (*production)[6]='R';
        }
        if (!ranged.empty()) shoot(turn,orders,ranged);
    }
};

inline int run(zoo::Config config, Policy policy=Policy::Melee, int start=1, int reserve=0) {
    const auto setup=hrw::read_setup();
    zoo::Strategy base(setup,config);
    RangedPolicy ranged(setup);
    hrw::ready();
    hrw::Turn turn;
    while (hrw::read_turn(turn)) {
        auto view=turn;
        for (auto& unit : view.units) if (unit.kind=="R") unit.kind="S";
        auto orders=base.orders(view);
        ranged.apply(turn,orders,policy,start,reserve);
        hrw::send(orders);
    }
    return 0;
}
}  // namespace research
