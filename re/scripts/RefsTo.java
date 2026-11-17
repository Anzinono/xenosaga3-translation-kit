// Lists all references to an address, prints the gp value and decompiles the referencing functions.
// Usage: ... -postScript RefsTo.java 0x551184 [maxFunctions]
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import java.util.*;

public class RefsTo extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        Address target = toAddr(args[0]);
        int max = args.length > 1 ? Integer.parseInt(args[1]) : 4;
        Register gp = currentProgram.getRegister("gp");
        var gpVal = currentProgram.getProgramContext().getRegisterValue(gp, toAddr("0x200000"));
        println("gp at 0x200000: " + (gpVal == null || !gpVal.hasValue() ? "unknown" : "0x" + gpVal.getUnsignedValue().toString(16)));
        Set<Function> funcs = new LinkedHashSet<>();
        for (Reference r : getReferencesTo(target)) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("Reference from " + r.getFromAddress() + " (" + r.getReferenceType() + ") in " + (f == null ? "?" : f.getName()));
            if (f != null) funcs.add(f);
        }
        DecompInterface d = new DecompInterface();
        d.openProgram(currentProgram);
        int n = 0;
        for (Function f : funcs) {
            if (n++ >= max) break;
            println("=== " + f.getName() + " @ " + f.getEntryPoint());
            println(d.decompileFunction(f, 120, monitor).getDecompiledFunction().getC());
        }
    }
}
