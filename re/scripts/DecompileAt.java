// Dekompiliert die Funktionen, die die angegebenen Adressen enthalten, und listet ihre Aufrufer.
// Aufruf: ... -postScript DecompileAt.java 0x299b34 [0x...]
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.program.model.listing.Function;
import ghidra.program.model.address.Address;
import ghidra.program.model.symbol.Reference;

public class DecompileAt extends GhidraScript {
    @Override
    public void run() throws Exception {
        DecompInterface d = new DecompInterface();
        d.openProgram(currentProgram);
        for (String a : getScriptArgs()) {
            Address addr = toAddr(a);
            Function f = getFunctionContaining(addr);
            if (f == null) { println("Keine Funktion bei " + a); continue; }
            println("=== " + f.getName() + " @ " + f.getEntryPoint() + " (enthaelt " + a + ")");
            StringBuilder callers = new StringBuilder();
            for (Reference r : getReferencesTo(f.getEntryPoint())) {
                Function c = getFunctionContaining(r.getFromAddress());
                callers.append(" ").append(c == null ? r.getFromAddress().toString() : c.getName() + "@" + c.getEntryPoint());
            }
            println("Aufrufer:" + callers);
            println(d.decompileFunction(f, 120, monitor).getDecompiledFunction().getC());
        }
    }
}
