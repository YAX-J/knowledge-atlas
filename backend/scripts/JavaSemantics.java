import com.sun.source.tree.*;
import com.sun.source.util.*;
import javax.lang.model.element.*;
import javax.tools.*;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Compiler-only helper. Input is a base64 TSV virtual repository; processors and emit are disabled. */
class JavaSemantics {
  static class Source extends SimpleJavaFileObject {
    final String content, path;
    Source(String path, String content) {super(URI.create("mem:///" + path.replace(" ","%20")),Kind.SOURCE);this.path=path;this.content=content;}
    public CharSequence getCharContent(boolean ignore) {return content;}
  }
  static String decode(String value) {return new String(Base64.getDecoder().decode(value),StandardCharsets.UTF_8);}
  static String encode(String value) {return Base64.getEncoder().encodeToString(value.getBytes(StandardCharsets.UTF_8));}
  public static void main(String[] args) throws Exception {
    var scanner=new Scanner(System.in,StandardCharsets.UTF_8);
    String selected=decode(scanner.nextLine());
    var sources=new ArrayList<Source>();
    while(scanner.hasNextLine()) {
      String[] parts=scanner.nextLine().split("\t",2);
      if(parts.length==2) sources.add(new Source(decode(parts[0]),decode(parts[1])));
    }
    var compiler=ToolProvider.getSystemJavaCompiler();
    if(compiler==null) throw new IllegalStateException("JDK required");
    var diagnostics=new DiagnosticCollector<JavaFileObject>();
    try(var manager=compiler.getStandardFileManager(diagnostics,null,StandardCharsets.UTF_8)) {
      var task=(JavacTask)compiler.getTask(null,manager,diagnostics,List.of("-proc:none","-implicit:none","-classpath","","--release","17"),null,sources);
      var units=new ArrayList<CompilationUnitTree>();
      task.parse().forEach(units::add);
      long syntaxErrors=diagnostics.getDiagnostics().stream().filter(item->item.getKind()==Diagnostic.Kind.ERROR).count();
      task.analyze();
      var trees=Trees.instance(task);
      for(var unit:units) {
        String sourcePath=unit.getSourceFile().toUri().getPath().substring(1);
        if(!sourcePath.equals(selected)) continue;
        new TreePathScanner<Void,Void>() {
          void record(Tree tree,String expression) {
            long position=trees.getSourcePositions().getStartPosition(unit,tree);
            long callEnd=trees.getSourcePositions().getEndPosition(unit,tree);
            if(position<0 || callEnd<position) return; // Ignore compiler-generated implicit calls.
            var element=trees.getElement(getCurrentPath());
            var target=element==null?null:trees.getPath(element);
            if(target==null || !target.getCompilationUnit().getSourceFile().toUri().getScheme().equals("mem")) {
              System.out.println(unit.getLineMap().getLineNumber(position)+"\t"+unit.getLineMap().getColumnNumber(position)+"\t"+encode(expression)+"\t\t0\t\t0\t");
              return;
            }
            String destination=target.getCompilationUnit().getSourceFile().toUri().getPath().substring(1);
            long targetPosition=trees.getSourcePositions().getStartPosition(target.getCompilationUnit(),target.getLeaf());
            if(targetPosition<0) return;
            System.out.println(unit.getLineMap().getLineNumber(position)+"\t"+unit.getLineMap().getColumnNumber(position)+"\t"+
              encode(expression)+"\t"+encode(destination)+"\t"+target.getCompilationUnit().getLineMap().getLineNumber(targetPosition)+"\t"+
              encode(element.getSimpleName().toString())+"\t"+target.getCompilationUnit().getLineMap().getLineNumber(
                Math.max(targetPosition,trees.getSourcePositions().getEndPosition(target.getCompilationUnit(),target.getLeaf())-1))+"\t"+
              encode(targetPosition+":"+element.toString()));
          }
          public Void visitMethodInvocation(MethodInvocationTree tree,Void unused) {record(tree,tree.getMethodSelect().toString());return super.visitMethodInvocation(tree,unused);}
          public Void visitNewClass(NewClassTree tree,Void unused) {record(tree,tree.getIdentifier().toString());return super.visitNewClass(tree,unused);}
        }.scan(unit,null);
      }
      System.out.println("DIAGNOSTICS\t"+diagnostics.getDiagnostics().size());
      System.out.println("SYNTAX_ERRORS\t"+syntaxErrors);
    }
  }
}
