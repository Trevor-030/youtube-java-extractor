public class Main {
    public static void main(String[] args) {

        // static = Modifies a variable or method belong to the class,

        Friend friend1 = new Friend("Spongebob");
        Friend friend2 = new Friend("Patrick");
        Friend friend3 = new Friend("Squidward");
        Friend friend4 = new Friend("Sandy");

        Friend.showFriends();
    }
}

public class Friend {

    static int numOfFriends;
    String name;

    Friend(String name){
        this.name = name;
        numOfFriends++;
    }

    static void showFriends(){
        System.out.println("You have " + numOfFriends + " total friends");
    }
}
