public class Main {
    public static void main(String[] args) {

        // Interface = A blueprint for a class that specifies a set of abstract methods

        Rabbit rabbit = new Rabbit();
        Hawk hawk = new Hawk();
        Fish fish = new Fish();

        rabbit.flee();
        hawk.hunt();
        fish.flee();
        fish.hunt();

    }
}
public interface Prey {

    void flee();
}
public interface Predator {

    void hunt();
}
public class Rabbit implements Prey{

    @Override
    public void flee(){
        System.out.println("*The rabbit is running away*");
    }
}
public class Hawk implements Predator{

    @Override
    public void hunt(){
        System.out.println("*The hawk is hunting*");
    }
}
public class Fish implements Prey, Predator{

    @Override
    public void flee(){
        System.out.println("*The fish is swimming away*");
    }

    @Override
    public void hunt(){
        System.out.println("*The fish is hunting*");
    }
}
