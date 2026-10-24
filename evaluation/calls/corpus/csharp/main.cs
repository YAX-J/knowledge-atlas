public class Caller {
  public void run(Alpha a, dynamic unknown, bool flag) {
    Alpha.unique();
    a.save();
    unknown.save();
    external_missing();
    dynamic selected = flag ? (object)a : new Beta();
    selected.save();
  }
  extern void external_missing();
}
