public class Main {
    public static void main(String[] args) {

        // Inheritance = One class inherits the attributes and methods
        //                         from another class.

        Dog dog = new Dog();
        Cat cat = new Cat();
        Plant plant = new Plant();

    }
}
public class Organism {

    boolean isAlive;

    Organism(){
        isAlive = true;
    }
}
public class Plant extends Organism{

    void photosynthesize(){
        System.out.println("The plant absorbs sunlight");
    }
}
public class Animal extends Organism{

    void eat(){
        System.out.println("This animal is eating");
    }
}
public class Dog extends Animal{

    int lives = 1;

    void speak(){
        System.out.println("The dog goes *woof*");
    }
}
public class Cat extends Animal{

    int lives = 9;

    void speak(){
        System.out.println("The cat goes *meow*");
    }
}
