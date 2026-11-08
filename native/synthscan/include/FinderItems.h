#pragma once
#include <string>
#include <algorithm>
#include <cctype>
namespace FinderItems {
enum class Icon {Ship,Vehicle,Collectible,Armor,Clothing,Gun,Ammo,ShipGun,Component,Commodity,Consumable,Blueprint,Paint,Container,Equipment,Count};
inline Icon classify(std::string kind,std::string category,std::string type,std::string name,std::string record=""){
    auto lower=[](std::string& text){std::transform(text.begin(),text.end(),text.begin(),[](unsigned char c){return char(std::tolower(c));});};
    lower(kind);lower(category);lower(type);lower(name);lower(record);
    auto has=[](const std::string& text,const char* word){return text.find(word)!=std::string::npos;};
    if(kind=="blueprint")return Icon::Blueprint;
    if(kind=="ship")return Icon::Ship;if(kind=="vehicle")return Icon::Vehicle;
    if(has(type,"flair")||has(name,"plush")||has(name," model")||has(category,"collectible"))return Icon::Collectible;
    if(has(type,"char_armor")||type=="armor")return Icon::Armor;
    if(has(type,"char_clothing"))return Icon::Clothing;
    if(has(type,"magazine")||has(type,"ammo")||has(name,"magazine")||has(name,"ammunition"))return Icon::Ammo;
    if(has(type,"weaponpersonal"))return Icon::Gun;
    if((kind=="component"||has(record,"/ships/"))&&(has(type,"weapon")||has(type,"missile")||has(type,"turret")))return Icon::ShipGun;
    if(kind=="component"||has(category,"ship components"))return Icon::Component;
    if(kind=="material"||has(category,"commodit")||type=="resource")return Icon::Commodity;
    if(has(category,"consumable")||type=="food"||type=="drink"||has(type,"medical"))return Icon::Consumable;
    if(has(category,"paint")||type=="paints")return Icon::Paint;
    if(has(category,"cargo")||has(category,"container"))return Icon::Container;
    return Icon::Equipment;
}
}
