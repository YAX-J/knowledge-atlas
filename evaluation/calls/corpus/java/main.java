package bench;
interface Savable { void save(); }
class Caller {
  void run(Alpha a, Savable unknown, boolean flag) {
    Alpha.unique();
    a.save();
    unknown.save();
    External.missing();
    Savable selected = flag ? a : new Beta();
    selected.save();
  }
}
