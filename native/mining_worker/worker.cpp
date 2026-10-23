// SynthScan Native Mining worker, GPL-3.0-or-later.
// Reader/calculation authorship and licenses are preserved in vendor/.
#include "engine.h"
#include <iostream>
#include <string>
int main() {
    SetPriorityClass(GetCurrentProcess(),BELOW_NORMAL_PRIORITY_CLASS);
    SetProcessDPIAware();
    // Upstream diagnostics use cout. Keep them off the machine-readable stream.
    std::ostream protocol(std::cout.rdbuf());std::cout.rdbuf(std::cerr.rdbuf());
    try {
        Engine engine;std::string line;
        while(std::getline(std::cin,line)) {
            J req;std::string why;J response;
            try {
                if(line.size()>65536||!SCMiner::parseJson(line,req,why)||req.kind!=J::Kind::Object)throw std::runtime_error("Invalid request");
                auto result=engine.request(req);
                response=object({{"schema",j(1)},{"id",j(req.numberOr("id"))},{"ok",j(true)},{"result",result}});
            } catch(const std::exception& error) {
                response=object({{"schema",j(1)},{"id",j(req.numberOr("id"))},{"ok",j(false)},{"error",j(error.what())}});
            }
            protocol<<dump(response)<<'\n'<<std::flush;
        }
    } catch(const std::exception& error) {std::cerr<<error.what()<<std::endl;return 2;}
    return 0;
}
