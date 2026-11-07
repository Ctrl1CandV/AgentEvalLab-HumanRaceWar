// Small mining/transport example, intentionally not a strong bot.
#include "hrw.hpp"
#include <algorithm>
int main() {
    auto setup=hrw::read_setup(); hrw::ready();
    auto base=setup.bases().at(setup.you);
    std::set<int> returning;
    hrw::Turn t;
    while (hrw::read_turn(t)) {
        std::vector<std::string> orders;
        std::set<hrw::Pos> occupied, reserved;
        for (auto u:t.units) occupied.insert(u.pos());
        int population=0;
        for (auto u:t.units) {
            if(u.owner!=setup.you) continue;
            ++population;
            if(u.kind!="W") continue;
            if(u.carry==setup.params.at("CARRY_MAX")) returning.insert(u.id);
            if(u.carry==0) returning.erase(u.id);
            bool home=returning.count(u.id) || (u.carry>0 && t.ore.empty());
            std::vector<hrw::Pos> targets, goals;
            if(home) {
                targets.push_back(base);
                for(auto tower:t.towers) if(tower[2]==setup.you) targets.push_back({tower[0],tower[1]});
            } else for(auto [p,n]:t.ore) targets.push_back(p);
            auto mine=std::find_if(targets.begin(),targets.end(),[&](auto p){return hrw::distance(p,u.pos())==1;});
            if(!home && mine!=targets.end()) {
                orders.push_back("MINE "+std::to_string(u.id)+" "+std::to_string(mine->first)+" "+std::to_string(mine->second));
                continue;
            }
            for(auto p:targets) for(auto [d,n]:hrw::neighbors(p)) goals.push_back(n);
            auto blocked=occupied; blocked.erase(u.pos()); blocked.insert(reserved.begin(),reserved.end());
            auto distances=hrw::bfs(setup.rows,goals,blocked);
            if(!distances.count(u.pos()) || distances.at(u.pos())==0) continue;
            int best=distances.at(u.pos()); std::string direction; hrw::Pos dest;
            for(auto [d,n]:hrw::neighbors(u.pos()))
                if(distances.count(n) && distances.at(n)<best && !occupied.count(n) && !reserved.count(n)) {
                    best=distances.at(n); direction=d; dest=n;
                }
            if(!direction.empty()) { orders.push_back("MOVE "+std::to_string(u.id)+" "+direction); reserved.insert(dest); }
        }
        if(t.number%30==0 && t.players.at(setup.you)[0]>=setup.params.at("SOLDIER_COST")
                && population<setup.params.at("POP_CAP")) {
            bool spawned=false;
            for(int y=0;y<int(setup.rows.size()) && !spawned;++y) for(int x=0;x<int(setup.rows[y].size());++x)
                if(setup.rows[y][x]=='.' && hrw::distance(base,{x,y})<=setup.params.at("SPAWN_RANGE")
                        && !occupied.count({x,y}) && !reserved.count({x,y})) {
                    orders.push_back("SPAWN S "+std::to_string(x)+" "+std::to_string(y)); spawned=true; break;
                }
        }
        hrw::send(orders);
    }
}
