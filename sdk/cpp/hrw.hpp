#pragma once
// HRW v1: standard-library I/O and geometry, no strategy.
#include <array>
#include <iostream>
#include <map>
#include <queue>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
#include <cstdlib>

namespace hrw {
using Pos = std::pair<int, int>;
inline int distance(Pos a, Pos b) { return std::abs(a.first-b.first)+std::abs(a.second-b.second); }
inline std::vector<std::pair<std::string, Pos>> neighbors(Pos p) {
    auto [x,y] = p;
    return {{"N",{x,y-1}}, {"E",{x+1,y}}, {"S",{x,y+1}}, {"W",{x-1,y}}};
}
inline std::map<Pos,int> bfs(const std::vector<std::string>& rows, const std::vector<Pos>& starts,
                             const std::set<Pos>& blocked = {}) {
    std::map<Pos,int> result;
    std::queue<Pos> q;
    auto ground = [&](Pos p) {
        auto [x,y] = p;
        return y>=0 && y<int(rows.size()) && x>=0 && x<int(rows[y].size()) && rows[y][x]=='.'
               && !blocked.count(p);
    };
    for (auto p: starts) if (ground(p) && !result.count(p)) { result[p]=0; q.push(p); }
    while (!q.empty()) {
        auto p=q.front(); q.pop();
        for (auto [d,n]: neighbors(p)) if (ground(n) && !result.count(n)) {
            result[n]=result[p]+1; q.push(n);
        }
    }
    return result;
}
struct Setup {
    int version=0, you=-1;
    // Seeds are decimal strings: protocol seeds need not fit a C++ integer.
    std::string ruleset, seed;
    std::map<std::string,int> params, limits;
    std::vector<std::string> rows;
    std::map<Pos,int> ore;
    std::map<int,Pos> bases() const {
        std::map<int,Pos> b;
        for (int y=0; y<int(rows.size()); ++y) for (int x=0; x<int(rows[y].size()); ++x)
            if (rows[y][x]>='0' && rows[y][x]<='9') b[rows[y][x]-'0']={x,y};
        return b;
    }
};
struct Unit { int id, owner; std::string kind; int x,y,hp,carry; Pos pos() const { return {x,y}; } };
struct Turn {
    int number=0, bank=0;
    std::map<int,std::array<int,4>> players;
    std::vector<Unit> units;
    std::vector<std::array<int,4>> towers;
    std::map<Pos,int> ore;
    std::vector<std::string> events;
};
inline bool message(std::vector<std::string>& lines, std::istream& in) {
    lines.clear(); std::string line;
    while (std::getline(in,line)) {
        if (!line.empty() && line.back()=='\r') line.pop_back();
        std::istringstream s(line); std::string k, extra; s>>k;
        if (k=="END" && !(s>>extra)) return true;
        if (!k.empty()) lines.push_back(line);
    }
    if (!lines.empty()) throw std::runtime_error("message ended before END");
    return false;
}
inline Setup read_setup(std::istream& in=std::cin) {
    std::vector<std::string> lines;
    if (!message(lines,in)) throw std::runtime_error("missing setup");
    Setup o;
    for (size_t i=0; i<lines.size(); ++i) {
        std::istringstream s(lines[i]); std::string k; s>>k;
        if (k=="HRW") s>>o.version;
        else if (k=="RULESET") s>>o.ruleset;
        else if (k=="YOU") s>>o.you;
        else if (k=="SEED") s>>o.seed;
        else if (k=="PARAM" || k=="LIMIT") { std::string n; int v; s>>n>>v; (k=="PARAM"?o.params:o.limits)[n]=v; }
        else if (k=="MAP") { int w,h; s>>w>>h; for(int y=0;y<h;++y) o.rows.push_back(lines.at(++i)); }
        else if (k=="ORE") { int x,y,n; s>>x>>y>>n; o.ore[{x,y}]=n; }
    }
    return o;
}
inline bool read_turn(Turn& o, std::istream& in=std::cin) {
    std::vector<std::string> lines;
    if (!message(lines,in)) return false;
    o=Turn{};
    for (auto& line: lines) {
        std::istringstream s(line); std::string k; s>>k;
        if (k=="TURN") s>>o.number;
        else if (k=="BANK") s>>o.bank;
        else if (k=="PLAYER") { int id; std::array<int,4> p; s>>id>>p[0]>>p[1]>>p[2]>>p[3]; o.players[id]=p; }
        else if (k=="UNIT") { Unit u; s>>u.id>>u.owner>>u.kind>>u.x>>u.y>>u.hp>>u.carry; o.units.push_back(u); }
        else if (k=="TOWER") { std::array<int,4> t; s>>t[0]>>t[1]>>t[2]>>t[3]; o.towers.push_back(t); }
        else if (k=="ORE") { int x,y,n; s>>x>>y>>n; o.ore[{x,y}]=n; }
        else if (k=="EVENT") { std::string e; std::getline(s,e); o.events.push_back(e); }
    }
    return true;
}
inline void ready(std::ostream& out=std::cout) { out<<"READY\n"<<std::flush; }
inline void send(const std::vector<std::string>& orders, std::ostream& out=std::cout) {
    for (const auto& s: orders) out<<s<<'\n';
    out<<"END\n"<<std::flush;
}
} // namespace hrw
