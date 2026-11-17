// Sets the gp register value for the whole code range (crt0: daddu gp, a0, zero with a0 = 0x5571F0).
// Usage (before analysis): ... -preScript SetGp.java [0x5571f0]
import ghidra.app.script.GhidraScript;
import ghidra.program.model.lang.Register;
import ghidra.program.model.mem.MemoryBlock;
import java.math.BigInteger;

public class SetGp extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        BigInteger gp = new BigInteger(args.length > 0 ? args[0].replace("0x", "") : "5571f0", 16);
        Register reg = currentProgram.getRegister("gp");
        for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
            if (b.isExecute() && b.isInitialized()) {
                currentProgram.getProgramContext().setValue(reg, b.getStart(), b.getEnd(), gp);
                println("gp = 0x" + gp.toString(16) + " fuer " + b.getName());
            }
        }
    }
}
