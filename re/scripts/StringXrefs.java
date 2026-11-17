// Sucht Strings, die einen Suchbegriff enthalten, und dekompiliert die Funktionen, die darauf verweisen.
// Aufruf: ... -postScript StringXrefs.java <Suchbegriff> [maxFunktionen]
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.program.model.data.StringDataInstance;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.Reference;
import ghidra.program.util.DefinedStringIterator;
import java.util.*;

public class StringXrefs extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        String needle = args.length > 0 ? args[0] : "font";
        int max = args.length > 1 ? Integer.parseInt(args[1]) : 5;
        DecompInterface d = new DecompInterface();
        d.openProgram(currentProgram);
        Set<Function> seen = new LinkedHashSet<>();
        for (Data s : DefinedStringIterator.forProgram(currentProgram)) {
            String v = StringDataInstance.getStringDataInstance(s).getStringValue();
            if (v == null || !v.contains(needle)) continue;
            println("STRING " + s.getAddress() + " \"" + v + "\"");
            for (Reference r : getReferencesTo(s.getAddress())) {
                Function f = getFunctionContaining(r.getFromAddress());
                println("  xref " + r.getFromAddress() + " in " + (f == null ? "?" : f.getName() + "@" + f.getEntryPoint()));
                if (f != null) seen.add(f);
            }
        }
        int n = 0;
        for (Function f : seen) {
            if (n++ >= max) break;
            println("=== " + f.getName() + " @ " + f.getEntryPoint());
            println(d.decompileFunction(f, 120, monitor).getDecompiledFunction().getC());
        }
    }
}
