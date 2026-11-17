// Gibt eine Kurzübersicht des analysierten Programms aus und dekompiliert den Einstiegspunkt.
// Aufruf: tools\ghidra-headless.bat re\ghidra xs3 -process SLUS_213.89 -noanalysis -scriptPath re\scripts -postScript Uebersicht.java
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.address.Address;

public class Uebersicht extends GhidraScript {
    @Override
    public void run() throws Exception {
        println("Sprache: " + currentProgram.getLanguageID());
        println("Funktionen: " + currentProgram.getFunctionManager().getFunctionCount());
        println("Speicherbloecke:");
        for (var b : currentProgram.getMemory().getBlocks()) {
            println("  " + b.getName() + " " + b.getStart() + "-" + b.getEnd());
        }
        Address entry = currentProgram.getSymbolTable().getExternalEntryPointIterator().next();
        Function f = getFunctionAt(entry);
        DecompInterface d = new DecompInterface();
        d.openProgram(currentProgram);
        DecompileResults r = d.decompileFunction(f, 60, monitor);
        println("Einstiegspunkt " + entry + " (" + f.getName() + "):");
        println(r.getDecompiledFunction().getC());
    }
}
