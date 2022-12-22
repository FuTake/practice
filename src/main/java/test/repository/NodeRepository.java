package test.repository;

import org.springframework.data.neo4j.annotation.Query;
import org.springframework.data.neo4j.repository.Neo4jRepository;
import org.springframework.stereotype.Repository;
import test.domain.PO.Person;

import java.util.List;

@Repository
public interface NodeRepository extends Neo4jRepository<Person,Long> {
    @Query("match(n:Person) return n limit 10")
    List<Person> selectAll();

    @Query("MATCH(p:Person{name:$name}) return p")
    Person findByName(String name);
}
