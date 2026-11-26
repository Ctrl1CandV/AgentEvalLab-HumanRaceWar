#pragma once
// Prototype-only scoring policy layered over the unchanged public zoo strategy.
#include "strategy.hpp"

namespace activation {
enum class Policy { All, Fixed, Adaptive };

inline int planned_spending(const hrw::Setup& setup, const std::vector<std::string>& orders) {
    int sum = 0;
    for (const auto& text : orders) {
        if (text.starts_with("BUILD ")) sum += setup.params.at("TOWER_COST");
        else if (text.starts_with("SPAWN "))
            sum += setup.params.at(text.at(6) == 'W' ? "WORKER_COST" : "SOLDIER_COST");
    }
    return sum;
}

struct Adaptive {
    int prior_deposited = 0, prior_enemy_score = 0, income16 = 0, enemy_pace16 = 0;

    int reserve(const hrw::Setup& setup, const hrw::Turn& turn, hrw::Pos home,
                int owned, int rival, int price) {
        const int you = setup.you, enemy = 1-you;
        const auto& mine = turn.players.at(you);
        const auto& theirs = turn.players.at(enemy);
        income16 = (15*income16 + 16*(mine[3]-prior_deposited))/16;
        enemy_pace16 = (15*enemy_pace16 + 16*(theirs[1]-prior_enemy_score))/16;
        prior_deposited = mine[3];
        prior_enemy_score = theirs[1];

        const int left = setup.params.at("TURNS")-turn.number+1;
        const int soldier = setup.params.at("SOLDIER_COST");
        const int cost = owned*price;
        int enemy_near = 0, allied_near = 0;
        for (const auto& unit : turn.units) if (hrw::distance(home,unit.pos()) <= 12 && unit.kind == "S") {
            if (unit.owner == you) ++allied_near;
            else ++enemy_near;
        }
        const int emergency = std::clamp(enemy_near-allied_near,0,5)*soldier;
        const int gap = theirs[1]-mine[1];
        const int estimated_rival_pace16 = std::max(enemy_pace16, 6*rival);
        // Pressure = projected points needed vs. the number we could buy by
        // spending our realistically available cash and holding our towers.
        const int spendable = std::max(0, mine[0]-2*soldier)+income16*left/16;
        const int capacity = std::min(left*owned, spendable/price);
        const int target = std::max(0,gap+estimated_rival_pace16*left/16+1);
        const bool urgent = capacity > 0 && target*4 >= capacity*3;
        const bool sustainable = income16 >= 16*cost + 12*16;
        int reserve = left > 180 ? 5*soldier : left > 90 ? 3*soldier : left > 42 ? 2*soldier : soldier;
        if (sustainable) reserve -= soldier;
        if (urgent) reserve -= 2*soldier;
        if (left <= 15) reserve = 0;
        if (left > 18) reserve = std::max(reserve, emergency);
        if (left <= 35 && -gap > (rival+1)*left) reserve = std::max(reserve, 3*soldier);
        return std::max(0,reserve);
    }
};

inline int run(zoo::Config config, Policy policy = Policy::All, int start = 1, int savings = 0) {
    const auto setup = hrw::read_setup();
    zoo::Strategy strategy(setup, config);
    const auto home = setup.bases().at(setup.you);
    const auto p = setup.params.find("TOWER_ACTIVATION_COST");
    const int price = p == setup.params.end() ? 0 : p->second;
    Adaptive adaptive;
    hrw::ready();
    hrw::Turn turn;
    while (hrw::read_turn(turn)) {
        auto orders = strategy.orders(turn);
        if (price > 0) {
            std::vector<hrw::Pos> towers;
            int rival = 0;
            for (const auto& [x,y,owner,hp] : turn.towers) {
                if (owner == setup.you) towers.emplace_back(x,y);
                else ++rival;
            }
            int reserve = policy == Policy::Adaptive ?
                adaptive.reserve(setup,turn,home,int(towers.size()),rival,price) : savings;
            if (turn.number >= start) {
                // With a zero reserve, ask for all eligible towers. The engine
                // uses actual post-build energy including this turn's deposit.
                int limit = reserve == 0 ? int(towers.size()) :
                    std::max(0,turn.players.at(setup.you)[0]-planned_spending(setup,orders)-reserve)/price;
                // Home-relative, rotationally symmetric priority for equally
                // priced activations. The engine never reorders these requests.
                auto [x,y] = home;
                const int sign = std::pair(y,x) < std::pair(int(setup.rows.size())-1-y,
                    int(setup.rows.front().size())-1-x) ? 1 : -1;
                std::sort(towers.begin(),towers.end(),[sign,home](hrw::Pos a,hrw::Pos b) {
                    return std::tuple(hrw::distance(home,a),sign*a.second,sign*a.first) <
                           std::tuple(hrw::distance(home,b),sign*b.second,sign*b.first);
                });
                for (int i = 0; i < limit && i < int(towers.size()); ++i) {
                    auto [tx,ty] = towers[i];
                    orders.push_back("ACTIVATE " + std::to_string(tx) + " " + std::to_string(ty));
                }
            }
        }
        hrw::send(orders);
    }
    return 0;
}
}  // namespace activation
