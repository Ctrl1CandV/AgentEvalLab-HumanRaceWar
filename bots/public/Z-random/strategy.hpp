#pragma once
// Public, one-step heuristics for the A-stage zoo. No search or opponent IDs.
#include <hrw.hpp>
#include <algorithm>
#include <cstdint>
#include <limits>
#include <tuple>

namespace zoo {
using hrw::Pos;
enum class Mode { Idle, Random, Miner, Rush, WorkerRush, Economy, Turtle, Towers, Harass, Balanced };
struct Config { Mode mode; int workers, builders, towers, attackTurn; };
struct Target { Pos pos; int hp; char kind; };

class Strategy {
    hrw::Setup setup;
    Config config;
    int w,h,n,you,other,workersGoal,assault;
    Pos home,enemy;
    bool flipped;
    std::uint64_t seed=1469598103934665603ULL, randomState;
    std::vector<std::array<int,4>> edges;
    std::vector<Pos> sites;
    std::vector<int> guardCells;
    std::map<Pos,std::vector<int>> distances;
    std::set<int> returning;
    std::map<int,int> stalled;
    static constexpr int inf=100000;
    int cell(Pos p) const { return p.second*w+p.first; }
    Pos pos(int p) const { return {p%w,p/w}; }
    int parameter(const char* key) const { return setup.params.at(key); }
    bool ground(Pos p) const { return p.first>=0 && p.first<w && p.second>=0 && p.second<h && setup.rows[p.second][p.first]=='.'; }
    static std::uint64_t mix(std::uint64_t x) {
        x=(x^(x>>30))*0xbf58476d1ce4e5b9ULL;
        x=(x^(x>>27))*0x94d049bb133111ebULL;
        return x^(x>>31);
    }
    std::uint64_t rank(Pos p) const {
        int code=flipped?(h-1-p.second)*w+(w-1-p.first):cell(p);
        return mix(seed+std::uint64_t(code));
    }
    int random(int bound) { randomState+=0x9e3779b97f4a7c15ULL; return int(mix(randomState)%bound); }
    std::vector<int> adjacent(Pos p) const {
        std::vector<int> result;
        for (auto [d,q]:hrw::neighbors(p)) if (ground(q)) result.push_back(cell(q));
        return result;
    }
    std::vector<int> bfs(const std::vector<int>& goals,const std::vector<unsigned char>& blocked={}) const {
        std::vector<int> d(n,inf), queue(n); int begin=0,end=0;
        for (int p:goals) if (d[p]==inf && (blocked.empty() || !blocked[p])) { d[p]=0; queue[end++]=p; }
        while (begin<end) {
            int p=queue[begin++];
            for (int q:edges[p]) if (q>=0 && d[q]==inf && (blocked.empty() || !blocked[q])) {
                d[q]=d[p]+1; queue[end++]=q;
            }
        }
        return d;
    }
    const std::vector<int>& distance(Pos feature) {
        auto it=distances.find(feature);
        if (it==distances.end()) it=distances.emplace(feature,bfs(adjacent(feature))).first;
        return it->second;
    }
    int featureWalk(Pos from,Pos to) {
        int result=inf;
        for (int p:adjacent(to)) result=std::min(result,distance(from)[p]);
        return result;
    }
    std::string command(const char* name,int id,Pos p) const {
        return std::string(name)+" "+std::to_string(id)+" "+std::to_string(p.first)+" "+std::to_string(p.second);
    }
public:
    Strategy(hrw::Setup s,Config c):setup(std::move(s)),config(c) {
        h=int(setup.rows.size()); w=int(setup.rows[0].size()); n=w*h;
        you=setup.you; other=1-you; home=setup.bases().at(you); enemy=setup.bases().at(other);
        flipped=cell(home)>cell(enemy);
        for (unsigned char ch:setup.seed) seed=(seed^ch)*1099511628211ULL;
        randomState=seed;
        workersGoal=config.workers; assault=config.attackTurn;
        if (config.mode==Mode::Balanced) {
            workersGoal+=int(mix(seed)%3)-1;
            assault+=int(mix(seed+1)%17)-8;
        }
        edges.resize(n);
        for (int p=0;p<n;++p) {
            edges[p].fill(-1);
            if (ground(pos(p))) {
                int k=0; for (auto [d,q]:hrw::neighbors(pos(p))) { if (ground(q)) edges[p][k]=cell(q); ++k; }
            }
            if (setup.rows[p/w][p%w]=='S') sites.push_back(pos(p));
        }
        distance(home); distance(enemy);
        for (auto [p,amount]:setup.ore) distance(p);
        for (auto p:sites) distance(p);
        // Idle defenders must not form a ring sealing the unloading ports.
        // Keep every shortest home-mine route clear; this is terrain geometry,
        // not a lookup of map names or opponents.
        std::vector<unsigned char> roads(n);
        for (auto [ore,amount]:setup.ore) if (hrw::distance(home,ore)<=8) {
            int length=featureWalk(home,ore);
            for (int p=0;p<n;++p) if (distance(home)[p]+distance(ore)[p]==length) roads[p]=1;
        }
        for (int p=0;p<n;++p) if (ground(pos(p)) && !roads[p] &&
                hrw::distance(pos(p),home)>=2 && hrw::distance(pos(p),home)<=5) guardCells.push_back(p);
    }

    std::vector<std::string> orders(const hrw::Turn& turn) {
        std::vector<std::string> out;
        if (config.mode==Mode::Idle) return out;
        std::vector<const hrw::Unit*> own,workers,soldiers;
        std::vector<Target> targets;
        std::vector<unsigned char> occupied(n),blocked(n);
        int enemySoldiers=0;
        for (const auto& u:turn.units) {
            occupied[cell(u.pos())]=blocked[cell(u.pos())]=1;
            if (u.owner==you) {
                own.push_back(&u);
                (u.kind=="W"?workers:soldiers).push_back(&u);
            } else {
                targets.push_back({u.pos(),u.hp,u.kind[0]});
                enemySoldiers+=u.kind=="S";
            }
        }
        std::set<Pos> built,claimed;
        std::vector<Pos> depots{home};
        for (auto t:turn.towers) {
            Pos p={t[0],t[1]}; built.insert(p);
            if (t[2]==you) depots.push_back(p); else targets.push_back({p,t[3],'T'});
        }
        targets.push_back({enemy,turn.players.at(other)[2],'B'});
        int energy=turn.players.at(you)[0];
        // All purposeful styles can use the free base shot defensively.
        const Target* shot=nullptr;
        for (const auto& t:targets) if ((t.kind=='W' || t.kind=='S') && hrw::distance(t.pos,home)<=parameter("BASE_FIRE_RANGE")) {
            if (!shot || std::make_tuple(t.hp,rank(t.pos))<std::make_tuple(shot->hp,rank(shot->pos))) shot=&t;
        }
        std::map<Pos,int> plannedDamage;
        if (shot && (config.mode!=Mode::Random || random(3)==0)) {
            out.push_back("FIRE "+std::to_string(shot->pos.first)+" "+std::to_string(shot->pos.second));
            plannedDamage[shot->pos]+=parameter("BASE_FIRE_DMG");
        }

        auto move=[&](const hrw::Unit& u,const std::vector<int>& goals) {
            int start=cell(u.pos()); blocked[start]=0;
            auto d=bfs(goals,blocked); int destination=-1, direction=-1;
            for (int k=0;k<4;++k) {
                int q=edges[start][k];
                if (q>=0 && !blocked[q] && d[q]<d[start] &&
                    (destination<0 || std::make_tuple(d[q],rank(pos(q)))<std::make_tuple(d[destination],rank(pos(destination))))) {
                    destination=q; direction=k;
                }
            }
            if (destination<0 && d[start]!=0 && ++stalled[u.id]>=3) {
                // Bounded local yielding, never teleporting or stepping into a feature.
                std::uint64_t best=0;
                for (int k=0;k<4;++k) {
                    int q=edges[start][k];
                    if (q>=0 && !blocked[q]) {
                        auto value=mix(rank(pos(q))+std::uint64_t(turn.number/3)+std::uint64_t(u.id/2));
                        if (destination<0 || value>best) { destination=q; direction=k; best=value; }
                    }
                }
            }
            if (destination>=0) {
                out.push_back("MOVE "+std::to_string(u.id)+" "+std::string(1,"NESW"[direction]));
                blocked[destination]=1; stalled[u.id]=0;
            } else blocked[start]=1;
        };
        std::map<Pos,int> miners;
        int builderCount=std::min(config.builders,std::max(0,int(workers.size())-(config.mode==Mode::Balanced?5:3)));
        std::set<int> builders;
        if (int(depots.size())-1<config.towers)
            for (int i=0;i<builderCount;++i) builders.insert(workers[workers.size()-1-i]->id);

        for (const auto* pointer:own) {
            const auto& u=*pointer; int start=cell(u.pos());
            std::vector<const Target*> adjacentEnemies;
            for (const auto& t:targets) if (hrw::distance(t.pos,u.pos())==1) adjacentEnemies.push_back(&t);
            bool workerCombat=config.mode==Mode::WorkerRush || config.mode==Mode::Balanced || config.mode==Mode::Turtle;
            if (config.mode==Mode::Random) {
                std::vector<std::string> choices{""};
                for (int k=0;k<4;++k) if (edges[start][k]>=0 && !blocked[edges[start][k]])
                    choices.push_back("MOVE "+std::to_string(u.id)+" "+std::string(1,"NESW"[k]));
                for (auto t:adjacentEnemies) choices.push_back(command("ATTACK",u.id,t->pos));
                if (u.kind=="W") {
                    if (u.carry<parameter("CARRY_MAX")) for (auto [p,amount]:turn.ore)
                        if (hrw::distance(p,u.pos())==1) choices.push_back(command("MINE",u.id,p));
                    if (energy>=parameter("TOWER_COST")) for (auto p:sites)
                        if (!built.count(p) && !claimed.count(p) && hrw::distance(p,u.pos())==1)
                            choices.push_back(command("BUILD",u.id,p));
                }
                auto canonical=[&](const std::string& text) {
                    if (text.empty()) return std::pair<std::string,int>{"",0};
                    std::istringstream input(text); std::string word; int id,x,y; input>>word>>id;
                    if (word=="MOVE") {
                        char direction; input>>direction;
                        int k=int(std::string("NESW").find(direction));
                        return std::pair<std::string,int>{word,(k+(flipped?2:0))%4};
                    }
                    input>>x>>y; int p=cell({x,y});
                    return std::pair<std::string,int>{word,flipped?n-1-p:p};
                };
                std::sort(choices.begin(),choices.end(),[&](const auto& a,const auto& b){return canonical(a)<canonical(b);});
                auto selected=choices[random(int(choices.size()))];
                if (!selected.empty()) {
                    out.push_back(selected);
                    if (selected.rfind("MOVE",0)==0) {
                        int k=int(std::string("NESW").find(selected.back())); blocked[start]=0; blocked[edges[start][k]]=1;
                    } else if (selected.rfind("BUILD",0)==0) {
                        std::istringstream input(selected); std::string word; int id,x,y; input>>word>>id>>x>>y;
                        claimed.insert({x,y}); energy-=parameter("TOWER_COST");
                    }
                }
                continue;
            }
            if (!adjacentEnemies.empty() && (u.kind=="S" || workerCombat)) {
                auto priority=[&](const Target* t) {
                    bool rush=config.mode==Mode::Rush || config.mode==Mode::WorkerRush;
                    int kind=rush?(t->kind=='B'?0:1):(t->kind=='B'?2:t->kind=='T'?1:0);
                    int remaining=t->hp;
                    if (config.mode==Mode::Balanced || config.mode==Mode::Turtle) remaining-=plannedDamage[t->pos];
                    return std::make_tuple(remaining<=0,kind,remaining,rank(t->pos));
                };
                auto target=*std::min_element(adjacentEnemies.begin(),adjacentEnemies.end(),[&](auto a,auto b){return priority(a)<priority(b);});
                out.push_back(command("ATTACK",u.id,target->pos));
                plannedDamage[target->pos]+=parameter(u.kind=="W"?"WORKER_DMG":"SOLDIER_DMG"); continue;
            }
            if (u.kind=="W" && config.mode!=Mode::WorkerRush) {
                if (u.carry>=parameter("CARRY_MAX")) returning.insert(u.id);
                if (u.carry==0) returning.erase(u.id);
                if (returning.count(u.id) || (u.carry && turn.ore.empty())) {
                    Pos best=home;
                    for (auto p:depots) if (std::make_tuple(distance(p)[start],rank(p))<std::make_tuple(distance(best)[start],rank(best))) best=p;
                    move(u,adjacent(best)); continue;
                }
                if (builders.count(u.id)) {
                    Pos site={-1,-1}; int best=inf;
                    for (auto p:sites) if (!built.count(p) && !claimed.count(p)) {
                        int route=distance(p)[start];
                        if (config.mode==Mode::Balanced && featureWalk(home,p)>featureWalk(enemy,p)+6) continue;
                        if (site.first<0 || std::make_tuple(route,rank(p))<std::make_tuple(best,rank(site))) { site=p; best=route; }
                    }
                    if (site.first>=0 && best<inf) {
                        claimed.insert(site);
                        if (hrw::distance(u.pos(),site)==1) {
                            if (energy>=parameter("TOWER_COST")) { out.push_back(command("BUILD",u.id,site)); energy-=parameter("TOWER_COST"); }
                        } else move(u,adjacent(site));
                        continue;
                    }
                }
                Pos ore={-1,-1}; int best=inf;
                for (auto [p,amount]:turn.ore) {
                    if (config.mode==Mode::Turtle && hrw::distance(home,p)>8) continue;
                    int homeDistance=inf;
                    for (auto depot:depots) for (int q:adjacent(p)) homeDistance=std::min(homeDistance,distance(depot)[q]);
                    int score=distance(p)[start]+homeDistance/2+miners[p]*5;
                    if (ore.first<0 || std::make_tuple(score,rank(p))<std::make_tuple(best,rank(ore))) { ore=p; best=score; }
                }
                if (ore.first>=0 && best<inf) {
                    ++miners[ore];
                    if (hrw::distance(ore,u.pos())==1) out.push_back(command("MINE",u.id,ore));
                    else move(u,adjacent(ore));
                }
                continue;
            }
            Pos goal=enemy;
            if (config.mode==Mode::Harass) {
                int best=inf;
                for (const auto& t:targets) if (t.kind=='W' || t.kind=='T') {
                    int score=hrw::distance(u.pos(),t.pos)+(t.kind=='T'?3:0)+(hrw::distance(enemy,t.pos)<=4?35:0);
                    if (score<best || (score==best && rank(t.pos)<rank(goal))) { goal=t.pos; best=score; }
                }
            }
            if (config.mode==Mode::Balanced) {
                int nearest=inf;
                for (const auto& t:targets) if ((t.kind=='S' || t.kind=='W') && distance(home)[cell(t.pos)]<=12) {
                    int d=distance(home)[cell(t.pos)];
                    if (d<nearest || (d==nearest && rank(t.pos)<rank(goal))) { goal=t.pos; nearest=d; }
                }
                if (nearest==inf && turn.number>=assault) {
                    int best=distance(enemy)[start];
                    for (const auto& t:targets) if (t.kind=='T') {
                        int d=distance(t.pos)[start]+8;
                        if (d<best || (d==best && rank(t.pos)<rank(goal))) { goal=t.pos; best=d; }
                    }
                }
                int guards=turn.number<assault?2:1;
                bool guard=enemySoldiers>0 && std::any_of(soldiers.begin(),soldiers.begin()+std::min(guards,int(soldiers.size())),[&](auto s){return s->id==u.id;});
                if (nearest==inf && guard && !guardCells.empty()) {
                    move(u,guardCells); continue;
                }
                if (nearest==inf && turn.number<assault) {
                    std::vector<int> rally;
                    int advance=std::max(6,featureWalk(enemy,home)/2-3), best=inf;
                    for (int p=0;p<n;++p) if (ground(pos(p)) && distance(home)[p]<=advance) best=std::min(best,distance(enemy)[p]);
                    for (int p=0;p<n;++p) if (ground(pos(p)) && distance(home)[p]<=advance && distance(enemy)[p]<=best+4) rally.push_back(p);
                    move(u,rally); continue;
                }
            }
            if (config.mode==Mode::Turtle) {
                const Target* intruder=nullptr; int nearest=inf;
                for (const auto& t:targets) if ((t.kind=='W' || t.kind=='S') && distance(home)[cell(t.pos)]<=10) {
                    int d=hrw::distance(u.pos(),t.pos);
                    if (!intruder || std::make_tuple(d,rank(t.pos))<std::make_tuple(nearest,rank(intruder->pos))) { intruder=&t; nearest=d; }
                }
                move(u,intruder?adjacent(intruder->pos):guardCells);
            } else move(u,adjacent(goal));
        }
        if (int(own.size())<parameter("POP_CAP") && config.mode!=Mode::Miner) {
            char kind='S';
            bool spawn=true;
            if (config.mode==Mode::Random) { kind=random(2)?'W':'S'; spawn=random(3)==0; }
            else if (config.mode==Mode::WorkerRush) kind='W';
            else if (config.mode==Mode::Towers) { kind='W'; spawn=int(workers.size())<workersGoal; }
            else if (config.mode==Mode::Economy) kind=int(workers.size())<workersGoal && turn.number<assault?'W':'S';
            else if (config.mode==Mode::Balanced) {
                int desired=std::min(parameter("POP_CAP")-workersGoal,std::max({3,enemySoldiers+3,turn.number/7}));
                if (int(soldiers.size())<std::min(3,enemySoldiers+1)) kind='S';
                else if (int(workers.size())<workersGoal) kind='W';
                else spawn=int(soldiers.size())<desired;
            } else if (config.mode==Mode::Turtle || config.mode==Mode::Harass) {
                if (int(workers.size())<workersGoal) kind='W';
                else if (config.mode==Mode::Harass) spawn=soldiers.size()<10;
                else spawn=int(soldiers.size())<std::min(12,int(guardCells.size()));
            }
            int cost=parameter(kind=='W'?"WORKER_COST":"SOLDIER_COST");
            int reserve=(builderCount && int(depots.size())-1<config.towers)?parameter("TOWER_COST"):0;
            if (config.mode==Mode::Balanced && int(soldiers.size())<enemySoldiers+1) reserve=0;
            if (spawn && energy>=cost+reserve) {
                int where=-1;
                for (int p=0;p<n;++p) if (ground(pos(p)) && !occupied[p] && !blocked[p] && hrw::distance(pos(p),home)<=parameter("SPAWN_RANGE"))
                    if (where<0 || std::make_tuple(distance(enemy)[p],rank(pos(p)))<std::make_tuple(distance(enemy)[where],rank(pos(where)))) where=p;
                if (where>=0) out.push_back(std::string("SPAWN ")+kind+" "+std::to_string(where%w)+" "+std::to_string(where/w));
            }
        }
        return out;
    }
};

inline int run(Config config) {
    auto setup=hrw::read_setup(); Strategy strategy(std::move(setup),config); hrw::ready();
    hrw::Turn turn;
    while (hrw::read_turn(turn)) hrw::send(strategy.orders(turn));
    return 0;
}
} // namespace zoo
